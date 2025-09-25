import os
import json
from datetime import datetime
from typing import List, Dict, Any
<<<<<<< HEAD
=======
import asyncio
>>>>>>> feature/apoorva-initial-upload

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from models import QuestionsDoc
from utils import (
    load_env,
    call_openai_json,
<<<<<<< HEAD
    extract_text_from_upload,
    extract_github_links,
    extract_pdf_links_from_bytes,
    fetch_github_stats,
    calculate_github_score,
=======
    call_openai_json_async,
    extract_text_from_upload,
    extract_github_links,
    extract_linkedin_links,
    extract_pdf_links_from_bytes,
    fetch_github_stats,
    fetch_github_stats_async,
    calculate_github_score,
    slugify,
>>>>>>> feature/apoorva-initial-upload
)

# Ensure env and data dir
load_env()
DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL_CRITERIA = os.getenv("OPENAI_MODEL_CRITERIA", "gpt-4o-mini")
OPENAI_MODEL_MATCH = os.getenv("OPENAI_MODEL_MATCH", "gpt-4o-mini")

app = FastAPI(title="HR Resume Ranker API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Debug helper to test GitHub extraction
class ExtractGithubBody(BaseModel):
    text: str


@app.post("/debug/extract_github")
def debug_extract_github(body: ExtractGithubBody) -> Dict[str, Any]:
    try:
        links = extract_github_links(body.text or "")
        return {"links": links}
    except Exception as e:
        return {"error": str(e)}


PROMPT_CRITERIA = """You will design {n} evaluation criteria (Yes/No questions) to assess resumes for THIS role.
Return a JSON that matches the schema exactly. No markdown, no extra text.

CONTEXT
-------
SENIORITY: {seniority}
JOB DESCRIPTION:
<<<JD>>>
{jd}
<<<END JD>>>

HR NOTES (optional):
<<<HR>>>
{hr}
<<<END HR>>>

PRINCIPLES
----------
- Focus on what matters for this role/seniority.
- Prefer impact/evidence over pedigree.
- Allow leniency (projects/OSS/internships can substitute for formal exp).
- Each criterion is atomic and phrased as a Yes/No question.
- Weights must be 0..1 and sum ~1 across criteria.

SCHEMA
------
{{
  "role_summary": "1-2 sentences",
  "seniority": "intern|junior|mid|senior|lead|principal",
  "total_criteria": {n},
  "criteria": [
    {{
      "id": "snake_case_identifier",
      "name": "Short title",
      "question": "Yes/No question",
      "rationale": "Why this check matters here",
      "expected_evidence": ["concrete","resume","signals"],
      "leniency_note": "Where leniency is allowed",
      "weight": 0.0,
      "fail_examples": ["example of failing wording"],
      "tags": ["skills","impact","agents","qa","3d","ownership","communication"]
    }}
  ]
}}

OUTPUT RULES
------------
- Output ONLY the JSON object.
- Each criterion MUST be atomic, auditable, and a YES/NO question.
- Weights must be within 0..1 and sum ≈ 1 across the criteria.

Now produce the JSON.
"""


class CriteriaRequest(BaseModel):
    jd: str
    hr: str = ""
    n: int = 8
    seniority: str = "intern"


@app.post("/criteria/generate")
<<<<<<< HEAD
def generate_criteria(req: CriteriaRequest) -> Dict[str, Any]:
=======
async def generate_criteria(req: CriteriaRequest) -> Dict[str, Any]:
>>>>>>> feature/apoorva-initial-upload
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set"}
    prompt = PROMPT_CRITERIA.format(
        n=req.n,
        seniority=req.seniority,
        jd=req.jd[:20000],
        hr=(req.hr if req.hr.strip() else "(none provided)")[:8000],
    )
<<<<<<< HEAD
    raw = call_openai_json(OPENAI_MODEL_CRITERIA, prompt, OPENAI_API_KEY)
=======
    raw = await call_openai_json_async(OPENAI_MODEL_CRITERIA, prompt, OPENAI_API_KEY)
>>>>>>> feature/apoorva-initial-upload
    obj = json.loads(raw)
    qdoc = QuestionsDoc(**obj)
    return qdoc.model_dump()


@app.post("/analyze")
async def analyze(
    jd: str = Form(""),
    hr: str = Form(""),
    criteria_json: str = Form(...),
    resumes: List[UploadFile] = File(...),
<<<<<<< HEAD
    require_github: bool = Form(True),
=======
    require_github: bool = Form(False),
>>>>>>> feature/apoorva-initial-upload
) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set"}

    try:
        criteria_doc: Dict[str, Any] = json.loads(criteria_json)
        crit_list = criteria_doc.get("criteria", [])
        questions_payload = [{"id": c["id"], "question": c["question"]} for c in crit_list]
    except Exception as e:
        return {"error": f"Invalid criteria_json: {e}"}

    # Prepare resumes
    resumes_payload: List[Dict[str, str]] = []
    resume_text_lookup: Dict[str, str] = {}
    resume_bytes_lookup: Dict[str, bytes] = {}
<<<<<<< HEAD
    for f in resumes:
        content = await f.read()
        try:
            text = extract_text_from_upload(f.filename, content)
        except Exception:
=======
    # Build payloads and mappings
    resume_id_map: Dict[str, str] = {}
    for f in resumes:
        print(f"--- Parsing file: {f.filename} ---")
        content = await f.read()
        try:
            text = extract_text_from_upload(f.filename, content)
            print(f"Successfully extracted text from {f.filename}. Length: {len(text)}")
        except Exception as e:
            print(f"!!! FAILED to extract text from {f.filename}: {e} !!!")
>>>>>>> feature/apoorva-initial-upload
            text = content.decode("utf-8", errors="ignore")
        text_limited = text[:20000]
        resumes_payload.append({"id": f.filename, "text": text_limited})
        resume_text_lookup[f.filename] = text_limited
        resume_bytes_lookup[f.filename] = content
<<<<<<< HEAD

    # Call OpenAI for matching
    # Build prompt same as Streamlit's OpenAIResumeMatcher
    def build_prompt() -> str:
        return f"""
=======
        # Normalized ID mapping for robust matching with model output
        resume_id_map[slugify(f.filename)] = f.filename

    # Pre-extract GitHub and LinkedIn links per resume (from text and embedded PDF links),
    # so we can fetch stats in parallel while we call OpenAI.
    gh_links_map: Dict[str, List[str]] = {}
    linkedin_links_map: Dict[str, List[str]] = {}
    for rid, text_src in resume_text_lookup.items():
        # Detect GitHub links from visible text
        gh_text_links = extract_github_links(text_src)
        # Detect LinkedIn links from visible text
        linkedin_text_links = extract_linkedin_links(text_src)
        
        # Detect links from embedded PDF hyperlinks if applicable
        pdf_links: List[str] = []
        try:
            if isinstance(rid, str) and rid.lower().endswith('.pdf'):
                raw_bytes = resume_bytes_lookup.get(rid, b"")
                if raw_bytes:
                    pdf_links = extract_pdf_links_from_bytes(raw_bytes)
        except Exception:
            pdf_links = []
        
        # Extract GitHub and LinkedIn from PDF links
        gh_pdf_links = extract_github_links("\n".join(pdf_links)) if pdf_links else []
        linkedin_pdf_links = extract_linkedin_links("\n".join(pdf_links)) if pdf_links else []
        
        # Union candidates while preserving order preference (text first)
        # GitHub links
        seen = set()
        gh_links: List[str] = []
        for url in gh_text_links + gh_pdf_links:
            if url not in seen:
                seen.add(url)
                gh_links.append(url)
        gh_links_map[rid] = gh_links
        
        # LinkedIn links
        seen = set()
        linkedin_links: List[str] = []
        for url in linkedin_text_links + linkedin_pdf_links:
            if url not in seen:
                seen.add(url)
                linkedin_links.append(url)
        linkedin_links_map[rid] = linkedin_links

    # Kick off GitHub stats fetch tasks asynchronously per resume (first candidate)
    github_tasks: Dict[str, asyncio.Task] = {}
    for rid, links in gh_links_map.items():
        if links:
            github_tasks[rid] = asyncio.create_task(fetch_github_stats_async(links[0]))

    # Filter resumes for OpenAI analysis based on GitHub requirement
    # Only send resumes with GitHub to OpenAI if require_github is True
    resumes_for_openai = []
    resumes_without_github = []
    
    for resume_data in resumes_payload:
        rid = resume_data["id"]
        has_github = len(gh_links_map.get(rid, [])) > 0
        
        if require_github and not has_github:
            # Skip OpenAI analysis for resumes without GitHub when required
            resumes_without_github.append(resume_data)
        else:
            # Include in OpenAI analysis
            resumes_for_openai.append(resume_data)
    
    # Call OpenAI for matching (async) - only for resumes that meet GitHub requirement
    openai_results = {}
    if resumes_for_openai:
        schema_example = '''
{
  "results": [
    {
      "resume_id": "<MUST MATCH EXACTLY one of the provided RESUMES id strings>",
      "answers": [
        {
          "criterion_id": "<id from QUESTIONS>",
          "question": "<question text>",
          "answer": "yes | no",
          "reasons": ["short reason 1", "short reason 2"]
        }
      ],
      "yes_count": 0,
      "no_count": 0,
      "majority_pass": true
    }
  ]
}
'''
        def build_prompt() -> str:
            return f"""
>>>>>>> feature/apoorva-initial-upload
You are an expert technical recruiter.

Evaluate each RESUME against each QUESTION using the provided JD and HR NOTES.
Answer strictly with JSON that matches the schema below.
For each resume, output yes/no per question and up to 3 short reasons (quotes or concise evidence).

CONTEXT
-------
JD:
{jd}

HR NOTES:
{hr}

<<<<<<< HEAD
QUESTIONS (array of objects {{id, question}}):
{json.dumps(questions_payload, ensure_ascii=False)}

RESUMES (array of objects {{id, text}}):
{json.dumps(resumes_payload, ensure_ascii=False)}

JSON SCHEMA TO OUTPUT
---------------------
{{
  "results": [
    {{
      "resume_id": "r1",
      "answers": [
        {{
          "criterion_id": "<id from QUESTIONS>",
          "question": "<question text>",
          "answer": "yes" | "no",
          "reasons": ["short reason 1", "short reason 2"]
        }}
      ],
      "yes_count": 0,
      "no_count": 0,
      "majority_pass": true
    }}
  ]
}}
"""

    prompt = build_prompt()
    raw = call_openai_json(OPENAI_MODEL_MATCH, prompt, OPENAI_API_KEY)
    out = json.loads(raw)

    # Persist full result
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    try:
        path = os.path.join(DATA_DIR, f"results_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
=======
QUESTIONS (array of objects with 'id' and 'question' keys):
{json.dumps(questions_payload, ensure_ascii=False)}

RESUMES (array of objects with 'id' and 'text' keys):
{json.dumps(resumes_for_openai, ensure_ascii=False)}

JSON SCHEMA TO OUTPUT
---------------------
{schema_example}
"""

        prompt = build_prompt()
        raw = await call_openai_json_async(OPENAI_MODEL_MATCH, prompt, OPENAI_API_KEY)
        openai_results = json.loads(raw)
        
        # Persist OpenAI result
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        try:
            path = os.path.join(DATA_DIR, f"results_{ts}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(openai_results, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    else:
        # No resumes to analyze with OpenAI
        openai_results = {"results": []}
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
>>>>>>> feature/apoorva-initial-upload

    # Compute grouping and GitHub detection per requirements
    results_out: List[Dict[str, Any]] = []
    total_q = len(questions_payload)
<<<<<<< HEAD
    for r in out.get("results", []):
        rid = r.get("resume_id")
        answers = r.get("answers", [])
        yes_count = sum(1 for a in answers if str(a.get("answer", "")).lower() == "yes")
        no_count = total_q - yes_count
        text_src = resume_text_lookup.get(rid, "")
        # Detect links from visible text
        gh_text_links = extract_github_links(text_src)
        # Detect links from embedded PDF hyperlinks if applicable
        pdf_links: List[str] = []
        try:
            if isinstance(rid, str) and rid.lower().endswith('.pdf'):
                raw_bytes = resume_bytes_lookup.get(rid, b"")
                if raw_bytes:
                    pdf_links = extract_pdf_links_from_bytes(raw_bytes)
        except Exception:
            pdf_links = []
        gh_pdf_links = extract_github_links("\n".join(pdf_links)) if pdf_links else []
        # Union candidates while preserving order preference (text first)
        seen = set()
        gh_links: List[str] = []
        for url in gh_text_links + gh_pdf_links:
            if url not in seen:
                seen.add(url)
                gh_links.append(url)
        has_github = len(gh_links) > 0
        github_url = gh_links[0] if has_github else ""

        # Fetch GitHub stats if available
        github_stats = {}
        github_score = 0.0
        if has_github:
            try:
                github_stats = fetch_github_stats(github_url)
                github_score = calculate_github_score(github_stats)
            except Exception as e:
                print(f"Error fetching GitHub stats for {github_url}: {e}")
=======
    # Collect GitHub stats results (only for resumes we started tasks for)
    github_stats_map: Dict[str, Dict[str, Any]] = {}
    if github_tasks:
        done = await asyncio.gather(*github_tasks.values(), return_exceptions=True)
        for rid, res in zip(github_tasks.keys(), done):
            if isinstance(res, dict):
                github_stats_map[rid] = res
            else:
                github_stats_map[rid] = {}

    # Process OpenAI results for resumes that were analyzed
    for r in openai_results.get("results", []):
        rid_raw = r.get("resume_id") or ""
        rid_norm = slugify(str(rid_raw))
        rid = resume_id_map.get(rid_norm, rid_raw)
        answers = r.get("answers", [])
        yes_count = sum(1 for a in answers if str(a.get("answer", "")).lower() == "yes")
        no_count = total_q - yes_count
        gh_links = gh_links_map.get(rid, [])
        has_github = len(gh_links) > 0
        github_url = gh_links[0] if has_github else ""

        # Retrieve GitHub stats from async tasks map if available
        github_stats = github_stats_map.get(rid, {}) if has_github else {}
        github_score = calculate_github_score(github_stats) if github_stats else 0.0
>>>>>>> feature/apoorva-initial-upload
        # If stats could not be fetched (404 or invalid), treat as no valid GitHub
        if has_github and not github_stats:
            has_github = False
            github_url = ""
            github_score = 0.0

        # Grouping logic
        from math import ceil
        if require_github and not has_github:
            group = "rejected"
            group_reason = "Rejected: GitHub missing and GitHub is required."
        elif yes_count == 0:
            group = "rejected"
            group_reason = "Rejected: none of the criteria were met."
        elif yes_count == total_q:
            group = "strongly_consider"
            group_reason = "Strongly consider: all criteria were met."
        elif yes_count >= ceil(total_q / 2):
            group = "potential_fit"
            group_reason = "Potential fit: majority of criteria were met."
        else:
            group = "rejected"
            group_reason = "Rejected: fewer than half of the criteria were met."

<<<<<<< HEAD
=======
        # Add LinkedIn data
        linkedin_links = linkedin_links_map.get(rid, [])
        has_linkedin = len(linkedin_links) > 0
        linkedin_url = linkedin_links[0] if has_linkedin else ""

>>>>>>> feature/apoorva-initial-upload
        results_out.append({
            "resume_id": rid,
            "answers": answers,
            "yes_count": yes_count,
            "no_count": no_count,
            "has_github": has_github,
            "github_url": github_url,
            "github_candidates": gh_links,
            "github_stats": github_stats,
            "github_score": github_score,
<<<<<<< HEAD
=======
            "has_linkedin": has_linkedin,
            "linkedin_url": linkedin_url,
            "linkedin_candidates": linkedin_links,
>>>>>>> feature/apoorva-initial-upload
            "group": group,
            "group_reason": group_reason,
        })

<<<<<<< HEAD
=======
    # Process resumes without GitHub that were skipped from OpenAI analysis
    for resume_data in resumes_without_github:
        rid = resume_data["id"]
        gh_links = gh_links_map.get(rid, [])
        linkedin_links = linkedin_links_map.get(rid, [])
        has_linkedin = len(linkedin_links) > 0
        linkedin_url = linkedin_links[0] if has_linkedin else ""
        
        # Create dummy "no" answers for all criteria
        dummy_answers = []
        for q in questions_payload:
            dummy_answers.append({
                "criterion_id": q["id"],
                "question": q["question"],
                "answer": "no",
                "reasons": ["No GitHub profile found - criteria evaluation skipped"]
            })

        results_out.append({
            "resume_id": rid,
            "answers": dummy_answers,
            "yes_count": 0,
            "no_count": total_q,
            "has_github": False,
            "github_url": "",
            "github_candidates": [],
            "github_stats": {},
            "github_score": 0.0,
            "has_linkedin": has_linkedin,
            "linkedin_url": linkedin_url,
            "linkedin_candidates": linkedin_links,
            "group": "rejected",
            "group_reason": "Rejected: GitHub missing and GitHub is required.",
        })

>>>>>>> feature/apoorva-initial-upload
    return {"results": results_out, "timestamp": ts}


@app.get("/artifacts/results")
def list_results() -> Dict[str, Any]:
    try:
        files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("results_") and f.endswith(".json")])
        return {"files": files}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/artifacts/criteria")
def list_criteria() -> Dict[str, Any]:
    try:
        files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("criteria_final_") and f.endswith(".json")])
        return {"files": files}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/artifacts/download")
def download_artifact(kind: str = Query(..., pattern="^(results|criteria)$"), file: str = Query(...)):
    fname_prefix = "results_" if kind == "results" else "criteria_final_"
    if not (file.startswith(fname_prefix) and file.endswith(".json")):
        return JSONResponse(status_code=400, content={"error": "invalid file name"})
    path = os.path.join(DATA_DIR, file)
    if not os.path.exists(path):
        return JSONResponse(status_code=404, content={"error": "not found"})
    return FileResponse(path, media_type="application/json", filename=file)
