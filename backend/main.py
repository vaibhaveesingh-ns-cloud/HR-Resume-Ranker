import os
import json
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from models import QuestionsDoc
from utils import load_env, call_openai_json, extract_text_from_upload

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
    raw = call_openai_json(OPENAI_MODEL_CRITERIA, prompt, OPENAI_API_KEY)
    obj = json.loads(raw)
    qdoc = QuestionsDoc(**obj)
    return qdoc.model_dump()


@app.post("/analyze")
async def analyze(
    jd: str = Form(""),
    hr: str = Form(""),
    criteria_json: str = Form(...),
    resumes: List[UploadFile] = File(...),
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
    for f in resumes:
        content = await f.read()
        try:
            text = extract_text_from_upload(f.filename, content)
        except Exception:
            text = content.decode("utf-8", errors="ignore")
        resumes_payload.append({"id": f.filename, "text": text[:20000]})

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

    return {"results": out.get("results", []), "timestamp": ts}


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
