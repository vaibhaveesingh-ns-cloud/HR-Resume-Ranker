import os
import json
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .models import QuestionsDoc
from .utils import (
    load_env,
    call_openai_json,
    extract_text_from_upload,
    extract_github_links,
    extract_pdf_links_from_bytes,
    fetch_github_stats,
    calculate_github_score,
)

# Ensure env and data dir
load_env()
DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL_CRITERIA = os.getenv("OPENAI_MODEL_CRITERIA", "gpt-4o-mini")
OPENAI_MODEL_MATCH = os.getenv("OPENAI_MODEL_MATCH", "gpt-4o-mini")
# Limits to keep prompts within safe size to avoid timeouts (tunable via env)
try:
    MAX_RESUME_CHARS = int(os.getenv("MAX_RESUME_CHARS", "8000"))
except Exception:
    MAX_RESUME_CHARS = 8000
try:
    MAX_TOTAL_RESUME_CHARS = int(os.getenv("MAX_TOTAL_RESUME_CHARS", "40000"))
except Exception:
    MAX_TOTAL_RESUME_CHARS = 40000

app = FastAPI(title="HR Resume Ranker API", version="1.0.0")
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
def generate_criteria(req: CriteriaRequest) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set"}
    prompt = PROMPT_CRITERIA.format(
        n=req.n,
        seniority=req.seniority,
        jd=req.jd[:20000],
        hr=(req.hr if req.hr.strip() else "(none provided)")[:8000],
    )
    try:
        raw = call_openai_json(OPENAI_MODEL_CRITERIA, prompt, OPENAI_API_KEY)
        obj = json.loads(raw)
        qdoc = QuestionsDoc(**obj)
        return qdoc.model_dump()
    except TimeoutError as e:
        return {"error": f"Criteria generation timed out: {e}"}
    except Exception as e:
        return {"error": f"Criteria generation failed: {e}"}


@app.post("/analyze")
async def analyze(
    jd: str = Form(""),
    hr: str = Form(""),
    criteria_json: str = Form(...),
    resumes: List[UploadFile] = File(...),
    require_github: bool = Form(True),
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
    total_chars = 0
    for f in resumes:
        content = await f.read()
        try:
            text = extract_text_from_upload(f.filename, content)
        except Exception:
            text = content.decode("utf-8", errors="ignore")
        # Enforce per-resume and total character budgets to keep prompt small
        text_limited = text[:MAX_RESUME_CHARS]
        if MAX_TOTAL_RESUME_CHARS > 0:
            remaining = MAX_TOTAL_RESUME_CHARS - total_chars
            if remaining <= 0:
                # Skip adding more text to prompt budget, but still keep bytes for PDF link extraction later
                text_limited = ""
            else:
                if len(text_limited) > remaining:
                    text_limited = text_limited[:remaining]
        total_chars += len(text_limited)
        resumes_payload.append({"id": f.filename, "text": text_limited})
        resume_text_lookup[f.filename] = text_limited
        resume_bytes_lookup[f.filename] = content

    # Call OpenAI for matching
    # Build prompt same as Streamlit's OpenAIResumeMatcher
    def build_prompt() -> str:
        return f"""
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
    try:
        raw = call_openai_json(OPENAI_MODEL_MATCH, prompt, OPENAI_API_KEY)
        out = json.loads(raw)
    except TimeoutError as e:
        return {"error": f"Analysis timed out: {e}"}
    except Exception as e:
        return {"error": f"Analysis failed: {e}"}

    # Persist full result
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    try:
        path = os.path.join(DATA_DIR, f"results_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    # Compute grouping and GitHub detection per requirements
    results_out: List[Dict[str, Any]] = []
    total_q = len(questions_payload)
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
            "group": group,
            "group_reason": group_reason,
        })

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
