import os
import re
import json
import tempfile
from typing import List

import httpx
from dotenv import load_dotenv
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document as DocxDocument
from io import BytesIO
from pypdf import PdfReader
import time


def load_env():
    # Load .env from project root if present
    load_dotenv()


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    return s.strip("_")


def extract_text_from_upload(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            return pdf_extract_text(tmp.name)
    if name.endswith(".docx"):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            doc = DocxDocument(tmp.name)
            return "\n".join(p.text for p in doc.paragraphs)
    return data.decode("utf-8", errors="ignore")


def call_openai_json(model: str, prompt: str, api_key: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are an exacting hiring evaluator. Output strictly valid JSON."},
            {"role": "user", "content": prompt},
        ],
    }
    # Allow configuration of timeout via env, default 60s
    try:
        timeout_s = float(os.getenv("OPENAI_TIMEOUT", "60"))
    except Exception:
        timeout_s = 60.0

    try:
        r = httpx.post(url, headers=headers, json=body, timeout=timeout_s)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        raise TimeoutError(f"OpenAI request timed out after {int(timeout_s)}s")
    except httpx.HTTPStatusError as e:
        # Surface useful error message if available
        try:
            err = e.response.json()
        except Exception:
            err = {"detail": e.response.text}
        raise RuntimeError(f"OpenAI HTTP {e.response.status_code}: {err}")


async def call_openai_json_async(model: str, prompt: str, api_key: str) -> str:
    """Async variant of call_openai_json using httpx.AsyncClient."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are an exacting hiring evaluator. Output strictly valid JSON."},
            {"role": "user", "content": prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def extract_github_links(text: str) -> List[str]:
    """Extract GitHub profile links from free text.
    - Supports http/https, optional www
    - Handles trailing punctuation ),.;:
    - Extracts username from repo/profile links and returns canonical profile URLs
    Returns a de-duplicated list of profile URLs like https://github.com/<username>
    """
    if not text:
        return []

    usernames: set[str] = set()
    # Common reserved GitHub path segments that are not user accounts
    reserved = {
        'features','topics','collections','trending','marketplace','about','pricing','sponsors','apps','login','join',
        'settings','organizations','orgs','enterprise','security','readme','explore','contact','blog','search',
        'customer-stories','events','sponsors','site','issues','pulls'
    }

    def _clean(segment: str) -> str:
        # strip trailing punctuation commonly stuck to URLs
        return segment.rstrip(').,;:\'\"')

    # 1) Full urls with protocol (http/https) and optional www
    for m in re.findall(r"https?://(?:www\.)?github\.com/([A-Za-z0-9._-]+)(?:/|\b)", text, flags=re.IGNORECASE):
        m = _clean(m)
        if len(m) > 2 and m.lower() not in reserved:
            usernames.add(m)

    # 2) Domain without protocol (with optional www)
    for m in re.findall(r"\b(?:www\.)?github\.com/([A-Za-z0-9._-]+)(?:/|\b)", text, flags=re.IGNORECASE):
        m = _clean(m)
        if len(m) > 2 and m.lower() not in reserved:
            usernames.add(m)

    # 3) Username mention patterns (avoid generic @mentions)
    # Explicit "github: username"
    for m in re.findall(r"github:\s*([A-Za-z0-9._-]+)", text, flags=re.IGNORECASE):
        m = _clean(m)
        if len(m) > 2 and m.lower() not in reserved:
            usernames.add(m)
    # Explicit "@username on github" or "@username github"
    for m in re.findall(r"@([A-Za-z0-9._-]+)\s+(?:on\s+)?github\b", text, flags=re.IGNORECASE):
        m = _clean(m)
        if len(m) > 2 and m.lower() not in reserved:
            usernames.add(m)

    # Build canonical profile URLs
    out: List[str] = []
    for u in usernames:
        url = f"https://github.com/{u}"
        out.append(url)
    return sorted(list(set(out)))


def extract_linkedin_links(text: str) -> List[str]:
    """Extract LinkedIn profile links from free text.
    - Supports http/https, optional www
    - Handles trailing punctuation ),.;:
    - Extracts profile URLs and returns canonical LinkedIn profile URLs
    Returns a de-duplicated list of profile URLs like https://linkedin.com/in/<username>
    """
    if not text:
        return []

    profiles: set[str] = set()
    
    def _clean(segment: str) -> str:
        # strip trailing punctuation commonly stuck to URLs
        return segment.rstrip(').,;:\'\"')

    # 1) Full LinkedIn URLs with protocol (http/https) and optional www
    # Matches: https://linkedin.com/in/username, https://www.linkedin.com/in/username
    for m in re.findall(r"https?://(?:www\.)?linkedin\.com/in/([A-Za-z0-9._-]+)(?:/|\b)", text, flags=re.IGNORECASE):
        m = _clean(m)
        if len(m) > 2:
            profiles.add(m)

    # 2) Domain without protocol (with optional www)
    # Matches: linkedin.com/in/username, www.linkedin.com/in/username
    for m in re.findall(r"\b(?:www\.)?linkedin\.com/in/([A-Za-z0-9._-]+)(?:/|\b)", text, flags=re.IGNORECASE):
        m = _clean(m)
        if len(m) > 2:
            profiles.add(m)

    # 3) Username mention patterns
    # Explicit "linkedin: username" or "LinkedIn: username"
    for m in re.findall(r"linkedin:\s*([A-Za-z0-9._-]+)", text, flags=re.IGNORECASE):
        m = _clean(m)
        if len(m) > 2:
            profiles.add(m)
    
    # Explicit "@username on linkedin" or "@username linkedin"
    for m in re.findall(r"@([A-Za-z0-9._-]+)\s+(?:on\s+)?linkedin\b", text, flags=re.IGNORECASE):
        m = _clean(m)
        if len(m) > 2:
            profiles.add(m)

    # Build canonical profile URLs
    out: List[str] = []
    for u in profiles:
        url = f"https://linkedin.com/in/{u}"
        out.append(url)
    return sorted(list(set(out)))


def extract_pdf_links_from_bytes(data: bytes) -> List[str]:
    """Extract URLs from PDF link annotations.
    Returns a list of raw URLs as found in annotations.
    """
    try:
        reader = PdfReader(BytesIO(data))
        links: List[str] = []
        for page in reader.pages:
            annots = page.get("/Annots", [])
            for a in annots or []:
                try:
                    obj = a.get_object()
                    if obj.get("/Subtype") == "/Link":
                        action = obj.get("/A")
                        if action and action.get("/S") == "/URI":
                            uri = action.get("/URI")
                            if isinstance(uri, str):
                                links.append(uri.strip())
                except Exception:
                    continue
        return list(dict.fromkeys(links))
    except Exception:
        return []


def fetch_github_stats(github_url: str) -> dict:
    """Fetch GitHub user statistics for ranking.
    Returns dict with stats or empty dict if failed.
    """
    if not github_url or not github_url.startswith('https://github.com/'):
        return {}
    
    try:
        # Extract username from URL
        parts = github_url.replace('https://github.com/', '').split('/')
        if not parts or not parts[0]:
            return {}
        username = parts[0]
        
        # GitHub API call (no auth needed for public data)
        import httpx
        headers = {}
        # Optional: use GITHUB_TOKEN to increase rate limit
        token = os.getenv('GITHUB_TOKEN', '').strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["Accept"] = "application/vnd.github+json"

        with httpx.Client(timeout=15, headers=headers) as client:
            # Get user info
            user_resp = client.get(f"https://api.github.com/users/{username}")
            if user_resp.status_code != 200:
                return {}
            
            user_data = user_resp.json()
            
            # Get user repos (first page only for performance)
            repos_resp = client.get(f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated")
            repos_data = repos_resp.json() if repos_resp.status_code == 200 else []
            
            # Calculate stats
            total_stars = sum(repo.get('stargazers_count', 0) for repo in repos_data)
            total_forks = sum(repo.get('forks_count', 0) for repo in repos_data)
            public_repos = user_data.get('public_repos', 0)
            followers = user_data.get('followers', 0)
            following = user_data.get('following', 0)
            
            # Recent activity score (repos updated in last year)
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=365)
            recent_repos = 0
            for repo in repos_data:
                if repo.get('updated_at'):
                    try:
                        updated = datetime.fromisoformat(repo['updated_at'].replace('Z', '+00:00'))
                        if updated > cutoff:
                            recent_repos += 1
                    except:
                        continue
            
            return {
                'username': username,
                'public_repos': public_repos,
                'followers': followers,
                'following': following,
                'total_stars': total_stars,
                'total_forks': total_forks,
                'recent_activity': recent_repos,
                'profile_created': user_data.get('created_at', ''),
                'bio': user_data.get('bio', ''),
                'company': user_data.get('company', ''),
                'location': user_data.get('location', ''),
                'blog': user_data.get('blog', ''),
            }
    except Exception as e:
        print(f"Error fetching GitHub stats for {github_url}: {e}")
        return {}


def calculate_github_score(stats: dict) -> float:
    """Calculate a GitHub activity score from 0-100 based on various metrics."""
    if not stats:
        return 0.0
    
    score = 0.0
    
    # Repository count (0-20 points)
    repos = min(stats.get('public_repos', 0), 50)
    score += (repos / 50) * 20
    
    # Stars received (0-25 points)
    stars = min(stats.get('total_stars', 0), 500)
    score += (stars / 500) * 25
    
    # Followers (0-15 points)
    followers = min(stats.get('followers', 0), 100)
    score += (followers / 100) * 15
    
    # Recent activity (0-20 points)
    recent = min(stats.get('recent_activity', 0), 20)
    score += (recent / 20) * 20
    
    # Forks (0-10 points)
    forks = min(stats.get('total_forks', 0), 100)
    score += (forks / 100) * 10
    
    # Profile completeness (0-10 points)
    completeness = 0
    if stats.get('bio'): completeness += 2
    if stats.get('company'): completeness += 2
    if stats.get('location'): completeness += 2
    if stats.get('blog'): completeness += 2
    if stats.get('public_repos', 0) > 0: completeness += 2
    score += completeness
    
    return min(round(score, 1), 100.0)


# -----------------------------
# Async GitHub fetch with TTL cache
# -----------------------------

_GH_CACHE: dict[str, tuple[float, dict]] = {}
_GH_CACHE_TTL_SECONDS = 24 * 60 * 60  # 1 day


def _gh_cache_get(username: str) -> dict:
    now = time.time()
    item = _GH_CACHE.get(username)
    if not item:
        return {}
    ts, data = item
    if now - ts > _GH_CACHE_TTL_SECONDS:
        # expired
        try:
            del _GH_CACHE[username]
        except Exception:
            pass
        return {}
    return data


def _gh_cache_set(username: str, data: dict) -> None:
    _GH_CACHE[username] = (time.time(), data)


async def fetch_github_stats_async(github_url: str) -> dict:
    """Async GitHub stats fetcher with simple in-memory TTL cache.
    Returns dict with stats or empty dict if failed.
    """
    if not github_url or not github_url.startswith('https://github.com/'):
        return {}

    try:
        parts = github_url.replace('https://github.com/', '').split('/')
        if not parts or not parts[0]:
            return {}
        username = parts[0]

        cached = _gh_cache_get(username)
        if cached:
            return cached

        headers = {}
        token = os.getenv('GITHUB_TOKEN', '').strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["Accept"] = "application/vnd.github+json"

        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            user_resp = await client.get(f"https://api.github.com/users/{username}")
            if user_resp.status_code != 200:
                return {}
            user_data = user_resp.json()

            repos_resp = await client.get(
                f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"
            )
            repos_data = repos_resp.json() if repos_resp.status_code == 200 else []

        total_stars = sum(repo.get('stargazers_count', 0) for repo in repos_data)
        total_forks = sum(repo.get('forks_count', 0) for repo in repos_data)
        public_repos = user_data.get('public_repos', 0)
        followers = user_data.get('followers', 0)
        following = user_data.get('following', 0)

        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=365)
        recent_repos = 0
        for repo in repos_data:
            if repo.get('updated_at'):
                try:
                    updated = datetime.fromisoformat(repo['updated_at'].replace('Z', '+00:00'))
                    if updated > cutoff:
                        recent_repos += 1
                except Exception:
                    continue

        data = {
            'username': username,
            'public_repos': public_repos,
            'followers': followers,
            'following': following,
            'total_stars': total_stars,
            'total_forks': total_forks,
            'recent_activity': recent_repos,
            'profile_created': user_data.get('created_at', ''),
            'bio': user_data.get('bio', ''),
            'company': user_data.get('company', ''),
            'location': user_data.get('location', ''),
            'blog': user_data.get('blog', ''),
        }

        _gh_cache_set(username, data)
        return data
    except Exception as e:
        print(f"Error fetching GitHub stats (async) for {github_url}: {e}")
        return {}
