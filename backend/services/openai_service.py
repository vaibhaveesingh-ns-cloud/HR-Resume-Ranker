import os
import zipfile
import tempfile
import json
import asyncio
from typing import Dict, List, Any
from openai import OpenAI
from PyPDF2 import PdfReader
import re
from datetime import datetime
import logging

from models.schemas import Candidate, RejectedCandidate

class ChatGPTService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0
        self.window_start = datetime.now().timestamp()
        self.window_duration = 60  # 1 minute
        # OpenAI free/org default can be RPM=3. Allow env overrides.
        self.max_requests_per_window = int(os.getenv("OPENAI_MAX_RPM", "3"))
        # For RPM=3, safest base delay is ~21 seconds.
        self.base_delay = float(os.getenv("OPENAI_BASE_DELAY", "21"))

    async def _rate_limit(self):
        now = datetime.now().timestamp()
        if now - self.window_start >= self.window_duration:
            self.request_count = 0
            self.window_start = now
        if self.request_count >= self.max_requests_per_window:
            wait_time = self.window_duration - (now - self.window_start)
            if wait_time > 0:
                print(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self.request_count = 0
                self.window_start = datetime.now().timestamp()
        time_since_last = now - self.last_request_time
        if time_since_last < self.base_delay:
            wait_time = self.base_delay - time_since_last
            await asyncio.sleep(wait_time)
        self.request_count += 1
        self.last_request_time = datetime.now().timestamp()

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF with PyPDF2 and pdfminer fallback"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PdfReader(file)
                try:
                    if getattr(reader, 'is_encrypted', False):
                        reader.decrypt("")
                        logging.info(f"PDF was encrypted, attempted empty-password decrypt: {os.path.basename(pdf_path)}")
                except Exception as e:
                    logging.warning(f"Failed to decrypt PDF {os.path.basename(pdf_path)}: {e}")
                for page in reader.pages:
                    try:
                        piece = page.extract_text()
                        if piece:
                            text += piece + "\n"
                    except Exception as pe:
                        logging.warning(f"Failed to extract text from a page in {os.path.basename(pdf_path)}: {pe}")
        except Exception as e:
            logging.warning(f"PyPDF2 failed for {os.path.basename(pdf_path)}: {e}")
        if len(text.strip()) < 20:
            try:
                from pdfminer.high_level import extract_text as pdfminer_extract_text
                text2 = pdfminer_extract_text(pdf_path) or ""
                if len(text2.strip()) > len(text.strip()):
                    logging.info(f"Used pdfminer fallback for {os.path.basename(pdf_path)}")
                    text = text2
            except Exception as e:
                logging.warning(f"pdfminer fallback failed for {os.path.basename(pdf_path)}: {e}")
        text = re.sub(r"\s+", " ", text or "").strip()
        return text

    def extract_github_links(self, text: str) -> List[str]:
        """Re-use the same robust patterns as in GeminiService"""
        github_links = []
        text_clean = text.replace('\n', ' ').replace('\t', ' ')
        url_patterns = [
            r'https?://github\.com/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._/-]*)?',
            r'https?://www\.github\.com/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._/-]*)?'
        ]
        for pattern in url_patterns:
            github_links.extend(re.findall(pattern, text_clean, re.IGNORECASE))
        domain_patterns = [
            r'(?:www\.)?github\.com/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._/-]*)?',
            r'(?:^|\s)github\.com/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._/-]*)?(?:\s|$)'
        ]
        for pattern in domain_patterns:
            matches = re.findall(pattern, text_clean, re.IGNORECASE)
            for match in matches:
                clean_match = match.strip()
                if not clean_match.startswith(('http://', 'https://')):
                    github_links.append(f"https://{clean_match}")
        username_patterns = [
            r'github\s*:\s*([a-zA-Z0-9._-]+)',
            r'@([a-zA-Z0-9._-]+)\s*(?:\(?\s*(?:on\s+)?github\s*\)?)',
            r'github\s+@([a-zA-Z0-9._-]+)',
            r'github\s+(?:profile|account|handle)\s*:\s*([a-zA-Z0-9._-]+)',
            r'(?:^|\s)([a-zA-Z0-9._-]{3,})\s+on\s+github(?:\s|$)',
            r'github\s+(?:username|id|handle)\s*:\s*([a-zA-Z0-9._-]+)',
            r'(?:^|\s)git\s*:\s*([a-zA-Z0-9._-]{3,})(?:\s|$)',
        ]
        for pattern in username_patterns:
            for username in re.findall(pattern, text_clean, re.IGNORECASE):
                username = username.strip()
                if username and len(username) > 2 and username.lower() not in ['hub', 'com', 'www']:
                    github_links.append(f"https://github.com/{username}")
        email_pattern = r'([a-zA-Z0-9._-]+)@github\.com'
        for username in re.findall(email_pattern, text_clean, re.IGNORECASE):
            if username and len(username) > 2:
                github_links.append(f"https://github.com/{username}")
        contact_patterns = [
            r'[•·▪▫-]\s*github\s*[:\-]?\s*([a-zA-Z0-9._-]+)',
            r'(?:source\s+code|code|repository|repo)\s*:\s*(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9._-]+)',
        ]
        for pattern in contact_patterns:
            for username in re.findall(pattern, text_clean, re.IGNORECASE):
                username = username.strip()
                if username and len(username) > 2 and username.lower() not in ['hub', 'com', 'www', 'profile', 'account']:
                    github_links.append(f"https://github.com/{username}")
        normalized_links = []
        for link in github_links:
            normalized = self._normalize_github_url(link)
            if normalized and self.is_valid_github_url(normalized):
                normalized_links.append(normalized)
        seen_usernames = set()
        unique_links = []
        for link in normalized_links:
            username = link.replace('https://github.com/', '').split('/')[0]
            if username not in seen_usernames and link.count('/') == 3:
                seen_usernames.add(username)
                unique_links.append(link)
        for link in normalized_links:
            username = link.replace('https://github.com/', '').split('/')[0]
            if username not in seen_usernames:
                seen_usernames.add(username)
                unique_links.append(link)
        return unique_links

    def _normalize_github_url(self, url: str) -> str:
        if not url:
            return ""
        url = url.strip().rstrip('/')
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        if url.startswith('http://'):
            url = url.replace('http://', 'https://', 1)
        url = url.replace('https://www.github.com/', 'https://github.com/')
        if 'github.com/' not in url:
            return ""
        return url

    def is_valid_github_url(self, url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname != 'github.com':
                return False
            path = parsed.path.strip('/')
            if not path:
                return False
            parts = path.split('/')
            username = parts[0]
            reserved = { 'about','account','admin','api','apps','assets','blog','business','contact','dashboard','developer','docs','enterprise','explore','features','gist','help','home','join','login','logout','marketplace','new','notifications','organizations','pricing','privacy','search','security','settings','site','support','team','terms','topics','trending','users','www' }
            if username.lower() in reserved:
                return False
            import string
            valid_chars = string.ascii_letters + string.digits + '-'
            if not all(c in valid_chars for c in username):
                return False
            if username.startswith('-') or username.endswith('-'):
                return False
            if '--' in username:
                return False
            return True
        except Exception as e:
            logging.warning(f"Error validating GitHub URL {url}: {e}")
            return False

    async def analyze_resume(self, job_description: str, resume_text: str, github_links: List[str], file_name: str) -> Dict[str, Any]:
        await self._rate_limit()
        github_links_text = f"\n\n**DETECTED GITHUB LINKS:** {', '.join(github_links)}" if github_links else ""

        # To avoid hitting TPM limits, truncate very long inputs.
        def _truncate_text(text: str, max_chars: int) -> str:
            if not text:
                return ""
            text = text.strip()
            if len(text) <= max_chars:
                return text
            return text[:max_chars] + "\n...[truncated]"

        # Reasonable bounds (adjustable via env if needed)
        max_resume_chars = int(os.getenv("OPENAI_MAX_RESUME_CHARS", "6000"))
        max_jd_chars = int(os.getenv("OPENAI_MAX_JD_CHARS", "4000"))
        resume_text = _truncate_text(resume_text, max_resume_chars)
        job_description = _truncate_text(job_description, max_jd_chars)
        system_prompt = "You are an expert Talent Acquisition specialist. Return only valid JSON."
        user_prompt = f"""
You are an expert Talent Acquisition specialist analyzing resumes for AI Engineer (Intern) positions. Your task is to categorize candidates into three groups based on specific criteria.

Job Description:
---
{job_description}
---

Candidate Resume:
---
{resume_text}
---{github_links_text}

CLASSIFICATION GROUPS:
- Group 1: High potential (shortlist) - Score: 80-100
- Group 2: Silver medalist (Batch 2) - Score: 60-79  
- Group 3: Rejected (not suitable) - Score: 0-59

MANDATORY CRITERIA (Automatic rejection if not met):
1. GitHub link is mandatory - Absence leads to automatic Group 3 rejection

GITHUB LINK DETECTION INSTRUCTIONS:
- Look for GitHub URLs in various formats: https://github.com/username, github.com/username
- Check for embedded references like "GitHub: username", "@username on GitHub", or "github.com/username"
- Accept GitHub profile links, repository links, or any valid GitHub URL
- If multiple GitHub links are found, use the most appropriate profile URL
- Convert incomplete GitHub references to full URLs (e.g., "github.com/user" → "https://github.com/user")

PRIMARY EVALUATION CRITERIA:
2. Strong Python proficiency
3. AI Library experience
4. ML Model exposure (LLMs, NN, Diffusion bonus)
5. AI Fundamentals understanding
6. AI Project evidence

CLASSIFICATION LOGIC:
- Group 3: No GitHub link OR lacks basic Python/AI requirements
- Group 2: Has GitHub + meets 3-4 primary criteria
- Group 1: Has GitHub + meets 5-6 primary criteria

INSTRUCTIONS:
1. Thoroughly search for GitHub links in ALL formats
2. If any GitHub reference is found, extract and format it as a complete URL
3. Evaluate each primary criteria (pythonProficiency, aiLibraryExperience, mlExposure, aiProjectEvidence)
4. Assign appropriate group based on criteria met
5. Provide detailed justification
6. Extract candidate name or use 'Unknown Candidate'

Return your analysis in the following JSON format:
{{
    "candidateName": "string",
    "githubUrl": "string",
    "group": "string",
    "isQualified": boolean,
    "score": integer,
    "pythonProficiency": boolean,
    "aiLibraryExperience": boolean,
    "mlExposure": boolean,
    "aiProjectEvidence": boolean,
    "justification": "string",
    "rejectionReason": "string"
}}
"""
        try:
            # Simple retry/backoff for 429
            max_retries = 5
            backoff = 10.0  # seconds
            for attempt in range(max_retries):
                try:
                    resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.2,
                    )
                    result_text = resp.choices[0].message.content
                    if "```json" in result_text:
                        result_text = result_text.split("```json")[1].split("```")[0]
                    elif "```" in result_text:
                        result_text = result_text.split("```")[1].split("```")[0]
                    result = json.loads(result_text.strip())
                    result['fileName'] = file_name
                    return result
                except Exception as api_err:
                    msg = str(api_err)
                    if 'rate limit' in msg.lower() or '429' in msg:
                        # Backoff and retry
                        sleep_for = backoff * (1.5 ** attempt)
                        logging.warning(f"Rate limited on attempt {attempt+1}/{max_retries}. Backing off for {sleep_for:.1f}s")
                        asyncio.sleep(0)  # yield control
                        import time
                        time.sleep(sleep_for)
                        continue
                    else:
                        raise
            # If we exit loop without return, treat as failure
            raise RuntimeError("Exceeded retries due to rate limiting")
        except Exception as e:
            print(f"Error analyzing resume {file_name}: {e}")
            return {
                'candidateName': 'Processing Error',
                'githubUrl': '',
                'group': 'Group 3: Rejected',
                'isQualified': False,
                'score': 0,
                'pythonProficiency': False,
                'aiLibraryExperience': False,
                'mlExposure': False,
                'aiProjectEvidence': False,
                'justification': 'An error occurred while analyzing this resume.',
                'rejectionReason': 'Failed to process resume.',
                'fileName': file_name
            }

    async def rank_resumes(self, job_description: str, zip_file_path: str) -> Dict[str, List]:
        ranked_candidates = []
        rejected_candidates = []

        def _is_valid_pdf_file(path: str) -> bool:
            """Quick validation that the file looks like a real PDF by checking magic header"""
            try:
                if not os.path.isfile(path):
                    return False
                if os.path.getsize(path) < 16:  # too small to be a real PDF
                    return False
                with open(path, 'rb') as f:
                    return f.read(5) == b'%PDF-'
            except Exception:
                return False
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            pdf_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    # Skip hidden and macOS AppleDouble resource fork files
                    if file.startswith('._') or file.startswith('.'):
                        continue
                    if root.find('__MACOSX') != -1:
                        continue
                    if file.lower().endswith('.pdf'):
                        full_path = os.path.join(root, file)
                        if _is_valid_pdf_file(full_path):
                            pdf_files.append(full_path)
            print(f"Found {len(pdf_files)} PDF files to process")
            for i, pdf_path in enumerate(pdf_files):
                file_name = os.path.basename(pdf_path)
                print(f"Processing {i+1}/{len(pdf_files)}: {file_name}")
                resume_text = self.extract_text_from_pdf(pdf_path)
                if not resume_text.strip():
                    rejected_candidates.append(RejectedCandidate(
                        id=f"{file_name}-{datetime.now().timestamp()}",
                        name="Unknown Candidate",
                        reason="Could not extract text from PDF",
                        file_name=file_name
                    ))
                    continue
                github_links = self.extract_github_links(resume_text)
                # Early reject to save API calls and tokens if no GitHub link found
                if not github_links:
                    rejected_candidates.append(RejectedCandidate(
                        id=f"{file_name}-{datetime.now().timestamp()}",
                        name="Unknown Candidate",
                        reason="No valid GitHub profile found.",
                        file_name=file_name
                    ))
                    continue
                result = await self.analyze_resume(job_description, resume_text, github_links, file_name)
                candidate_id = f"{file_name}-{datetime.now().timestamp()}"
                is_url_valid = self.is_valid_github_url(result['githubUrl'])
                if (result['isQualified'] and is_url_valid and 
                    result['group'] in ['Group 1: High potential', 'Group 2: Silver medalist']):
                    ranked_candidates.append(Candidate(
                        id=candidate_id,
                        name=result['candidateName'],
                        github_url=result['githubUrl'],
                        group=result['group'],
                        score=result['score'],
                        python_proficiency=result['pythonProficiency'],
                        ai_library_experience=result['aiLibraryExperience'],
                        ml_exposure=result['mlExposure'],
                        ai_project_evidence=result['aiProjectEvidence'],
                        justification=result['justification'],
                        file_name=file_name
                    ))
                else:
                    reason = result['rejectionReason']
                    if result['isQualified'] and not is_url_valid:
                        reason = 'Invalid or malformed GitHub URL found.'
                    elif not reason:
                        reason = 'No valid GitHub profile found.'
                    rejected_candidates.append(RejectedCandidate(
                        id=candidate_id,
                        name=result['candidateName'],
                        reason=reason,
                        file_name=file_name
                    ))
        ranked_candidates.sort(key=lambda x: x.score, reverse=True)
        return {"ranked": ranked_candidates, "rejected": rejected_candidates}
