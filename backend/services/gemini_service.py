import os
import zipfile
import tempfile
import json
import asyncio
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from PyPDF2 import PdfReader
import re
from datetime import datetime

from models.schemas import Candidate, RejectedCandidate

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0
        self.window_start = datetime.now().timestamp()
        self.window_duration = 60  # 1 minute
        self.max_requests_per_window = 8
        self.base_delay = 3.0  # 3 seconds between requests

    async def _rate_limit(self):
        """Implement rate limiting for Gemini API"""
        now = datetime.now().timestamp()
        
        # Reset window if needed
        if now - self.window_start >= self.window_duration:
            self.request_count = 0
            self.window_start = now
        
        # If at limit, wait for window reset
        if self.request_count >= self.max_requests_per_window:
            wait_time = self.window_duration - (now - self.window_start)
            if wait_time > 0:
                print(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self.request_count = 0
                self.window_start = datetime.now().timestamp()
        
        # Ensure minimum delay between requests
        time_since_last = now - self.last_request_time
        if time_since_last < self.base_delay:
            wait_time = self.base_delay - time_since_last
            await asyncio.sleep(wait_time)
        
        self.request_count += 1
        self.last_request_time = datetime.now().timestamp()

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            print(f"Error extracting text from PDF {pdf_path}: {e}")
            return ""

    def extract_github_links(self, text: str) -> List[str]:
        """Extract GitHub links from resume text"""
        github_links = []
        
        # Pattern 1: Full HTTPS URLs
        https_pattern = r'https://github\.com/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._-]+)?'
        https_matches = re.findall(https_pattern, text, re.IGNORECASE)
        github_links.extend(https_matches)
        
        # Pattern 2: github.com without protocol
        domain_pattern = r'github\.com/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._-]+)?'
        domain_matches = re.findall(domain_pattern, text, re.IGNORECASE)
        for match in domain_matches:
            if not match.startswith('https://'):
                github_links.append(f"https://{match}")
        
        # Pattern 3: GitHub username patterns
        username_pattern = r'(?:github:\s*|@)([a-zA-Z0-9._-]+)(?:\s+(?:on\s+)?github)?'
        username_matches = re.findall(username_pattern, text, re.IGNORECASE)
        for username in username_matches:
            if username and len(username) > 2:
                github_links.append(f"https://github.com/{username}")
        
        # Remove duplicates
        return list(set(github_links))

    def is_valid_github_url(self, url: str) -> bool:
        """Validate GitHub URL"""
        if not url or not isinstance(url, str):
            return False
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.scheme == 'https' and parsed.hostname == 'github.com'
        except:
            return False

    async def analyze_resume(self, job_description: str, resume_text: str, github_links: List[str], file_name: str) -> Dict[str, Any]:
        """Analyze a single resume using Gemini API"""
        await self._rate_limit()
        
        github_links_text = f"\n\n**DETECTED GITHUB LINKS:** {', '.join(github_links)}" if github_links else ""
        
        prompt = f"""
You are an expert Talent Acquisition specialist analyzing resumes for AI Engineer (Intern) positions. Your task is to categorize candidates into three groups based on specific criteria.

**Job Description:**
---
{job_description}
---

**Candidate Resume:**
---
{resume_text}
---{github_links_text}

**CLASSIFICATION GROUPS:**
- **Group 1: High potential (shortlist)** - Score: 80-100
- **Group 2: Silver medalist (Batch 2)** - Score: 60-79  
- **Group 3: Rejected (not suitable)** - Score: 0-59

**MANDATORY CRITERIA (Automatic rejection if not met):**
1. **GitHub link is mandatory** - Absence leads to automatic Group 3 rejection

**GITHUB LINK DETECTION INSTRUCTIONS:**
- Look for GitHub URLs in various formats: https://github.com/username, github.com/username
- Check for embedded references like "GitHub: username", "@username on GitHub", or "github.com/username"
- Accept GitHub profile links, repository links, or any valid GitHub URL
- If multiple GitHub links are found, use the most appropriate profile URL
- Convert incomplete GitHub references to full URLs (e.g., "github.com/user" → "https://github.com/user")

**PRIMARY EVALUATION CRITERIA:**
2. **Strong Python proficiency** - Demonstrated through resume projects
3. **AI Library experience** - TensorFlow, PyTorch, NumPy, Pandas, Scikit-learn, Matplotlib, etc.
4. **ML Model exposure** - Especially LLMs. Neural Networks or Diffusion models are bonus points
5. **AI Fundamentals understanding** - Generative AI, Machine Learning, Deep Learning
6. **AI Project evidence** - Projects that validate AI domain proficiency

**CLASSIFICATION LOGIC:**
- **Group 3**: No GitHub link OR lacks basic Python/AI requirements
- **Group 2**: Has GitHub + meets 3-4 primary criteria with decent AI exposure
- **Group 1**: Has GitHub + meets 5-6 primary criteria with strong AI project evidence

**INSTRUCTIONS:**
1. Thoroughly search for GitHub links in ALL formats (URLs, embedded references, usernames)
2. If any GitHub reference is found, extract and format it as a complete URL
3. Evaluate each primary criteria (pythonProficiency, aiLibraryExperience, mlExposure, aiProjectEvidence)
4. Assign appropriate group based on criteria met
5. Provide detailed justification explaining the classification and GitHub link detection
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
            response = self.model.generate_content(prompt)
            result_text = response.text
            
            # Clean up the response text to extract JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            
            result = json.loads(result_text.strip())
            result['fileName'] = file_name
            return result
            
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
        """Process ZIP file and rank all resumes"""
        ranked_candidates = []
        rejected_candidates = []
        
        # Extract ZIP file
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find all PDF files
            pdf_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith('.pdf') and not file.startswith('__MACOSX'):
                        pdf_files.append(os.path.join(root, file))
            
            print(f"Found {len(pdf_files)} PDF files to process")
            
            # Process each PDF
            for i, pdf_path in enumerate(pdf_files):
                file_name = os.path.basename(pdf_path)
                print(f"Processing {i+1}/{len(pdf_files)}: {file_name}")
                
                # Extract text from PDF
                resume_text = self.extract_text_from_pdf(pdf_path)
                if not resume_text.strip():
                    rejected_candidates.append(RejectedCandidate(
                        id=f"{file_name}-{datetime.now().timestamp()}",
                        name="Unknown Candidate",
                        reason="Could not extract text from PDF",
                        file_name=file_name
                    ))
                    continue
                
                # Extract GitHub links
                github_links = self.extract_github_links(resume_text)
                
                # Analyze resume
                result = await self.analyze_resume(job_description, resume_text, github_links, file_name)
                
                # Process result
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
        
        # Sort ranked candidates by score
        ranked_candidates.sort(key=lambda x: x.score, reverse=True)
        
        return {
            "ranked": ranked_candidates,
            "rejected": rejected_candidates
        }
