import os, io, json, tempfile, re
from typing import List, Dict, Any, Literal, Optional
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
import httpx
from pydantic import BaseModel
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document as DocxDocument
import pandas as pd
import altair as alt

# ---------- Setup ----------
load_dotenv()
st.set_page_config(page_title="Resume Screener", layout="wide")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL_CRITERIA = os.getenv("OPENAI_MODEL_CRITERIA", "gpt-4o-mini")
OPENAI_MODEL_MATCH = os.getenv("OPENAI_MODEL_MATCH", "gpt-4o-mini")

# Data directory to persist JSON artifacts
DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------- Schemas ----------
class Criterion(BaseModel):
    id: str
    name: str
    question: str
    rationale: str
    expected_evidence: List[str]
    leniency_note: str
    weight: float
    fail_examples: List[str] = []
    tags: List[str] = []

class QuestionsDoc(BaseModel):
    role_summary: str
    seniority: Literal["intern","junior","mid","senior","lead","principal"]
    total_criteria: int
    criteria: List[Criterion]

SUMMARY_COLS = ["Resume", "Yes", "No", "Relevance"]

# ---------- Utils ----------
def extract_text_from_upload(file) -> str:
    name = file.name.lower()
    data = file.read()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
            tmp.write(data); tmp.flush()
            return pdf_extract_text(tmp.name)
    if name.endswith(".docx"):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            tmp.write(data); tmp.flush()
            doc = DocxDocument(tmp.name)
            return "\n".join(p.text for p in doc.paragraphs)
    return data.decode("utf-8", errors="ignore")

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    return s.strip("_")

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
    r = httpx.post(url, headers=headers, json=body, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ---------- Criteria generation ----------
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

def generate_criteria(jd: str, hr: str, n: int, seniority: str) -> QuestionsDoc:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set on the server/environment.")
    prompt = PROMPT_CRITERIA.format(
        n=n, seniority=seniority, jd=jd[:20000], hr=(hr if hr.strip() else "(none provided)")[:8000]
    )
    raw = call_openai_json(OPENAI_MODEL_CRITERIA, prompt, OPENAI_API_KEY)
    obj = json.loads(raw)
    return QuestionsDoc(**obj)

# ---------- Matcher (Yes/No per question, reasons hidden) ----------
class OpenAIResumeMatcher:
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", max_reasons: int = 3):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        self.api_key = api_key
        self.model_name = model_name
        self.max_reasons = max_reasons

    def _prompt(self, jd: str, hr: str, questions: List[Dict[str, str]], resumes: List[Dict[str, str]]) -> str:
        return f"""
You are an expert technical recruiter.

Evaluate each RESUME against each QUESTION using the provided JD and HR NOTES.
Answer strictly with JSON that matches the schema below.
For each resume, output yes/no per question and up to {self.max_reasons} short reasons (quotes or concise evidence).

CONTEXT
-------
JD:
{jd}

HR NOTES:
{hr}

QUESTIONS (array of objects {{id, question}}):
{json.dumps(questions, ensure_ascii=False)}

RESUMES (array of objects {{id, text}}):
{json.dumps(resumes, ensure_ascii=False)}

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

    def run(self, jd: str, hr: str, questions: List[Dict[str, str]], resumes: List[Dict[str,str]]) -> Dict[str, Any]:
        prompt = self._prompt(jd, hr, questions, resumes)
        raw = call_openai_json(self.model_name, prompt, self.api_key)
        out = json.loads(raw)
        if "results" not in out or not isinstance(out["results"], list):
            raise RuntimeError("Model returned invalid JSON (missing 'results').")
        return out

# ---------- UI (single page, JSON hidden by default) ----------
st.title("Resume Screener — Generate Criteria & Analyze")

# Step 1: JD/HR → generate criteria
st.header("Step 1 — Paste the Job Description and (optional) HR notes")
c1, c2 = st.columns(2)
with c1:
    seniority = st.selectbox("Seniority", ["intern","junior","mid","senior","lead","principal"], index=0)
with c2:
    n_criteria = st.slider("How many criteria?", 5, 10, 8, 1)

jd_input = st.text_area("Job Description (required)", height=220, placeholder="Paste the full JD…")
hr_input = st.text_area("HR Notes (optional)", height=120, placeholder="What should be emphasized…")

if st.button("Generate criteria"):
    if not jd_input.strip():
        st.error("Please paste the Job Description.")
    elif not OPENAI_API_KEY:
        st.error("Server is missing OPENAI_API_KEY. Please contact the admin.")
    else:
        try:
            qdoc = generate_criteria(jd_input, hr_input, n_criteria, seniority)
            st.session_state["criteria_doc"] = qdoc.model_dump()
            # Reset any prior finalization state
            st.session_state.pop("final_criteria_doc", None)
            st.success("Criteria generated.")
        except Exception as e:
            st.error(f"Could not generate criteria: {e}")

criteria_doc = st.session_state.get("criteria_doc")
final_criteria_doc = st.session_state.get("final_criteria_doc")

# Show only the QUESTIONS list (JSON hidden)
if criteria_doc:
    st.subheader("Criteria (questions) to be used")
    questions = [c["question"] for c in criteria_doc["criteria"]]
    for i, q in enumerate(questions, 1):
        st.markdown(f"{i}. {q}")

    # JSON is hidden by default; show only if asked
    if st.checkbox("Show full criteria JSON (advanced)", value=False):
        st.json(criteria_doc)

    # Allow download without revealing JSON on screen
    jbytes = json.dumps(criteria_doc, indent=2, ensure_ascii=False).encode("utf-8")
    st.download_button("Download criteria.json", jbytes, "criteria.json", "application/json")

    st.divider()
    st.subheader("Step 1A — Select and customize criteria (optional)")
    st.caption("Choose which criteria to keep, adjust weights, or add custom criteria. Then click 'Finalize criteria'.")

    # Selection state
    if "criteria_selection" not in st.session_state:
        st.session_state["criteria_selection"] = {c["id"]: True for c in criteria_doc["criteria"]}
    if "criteria_weights" not in st.session_state:
        st.session_state["criteria_weights"] = {c["id"]: float(c.get("weight", 0.1)) for c in criteria_doc["criteria"]}

    # Render checklist with weight editors
    for c in criteria_doc["criteria"]:
        with st.expander(f"{c['name']} — {c['question']}"):
            st.session_state["criteria_selection"][c["id"]] = st.checkbox(
                f"Include '{c['id']}'", value=st.session_state["criteria_selection"][c["id"]]
            )
            st.session_state["criteria_weights"][c["id"]] = st.slider(
                f"Weight for {c['id']}", 0.0, 1.0, float(st.session_state["criteria_weights"][c["id"]]), 0.01
            )
            st.write("Rationale:", c.get("rationale", ""))
            st.write("Expected evidence:", ", ".join(c.get("expected_evidence", [])))
            st.write("Leniency:", c.get("leniency_note", ""))

    st.markdown("---")
    st.markdown("Add a custom criterion")
    with st.form("add_custom_criterion"):
        custom_name = st.text_input("Name", key="custom_name")
        custom_question = st.text_area("Yes/No question", key="custom_question")
        custom_weight = st.slider("Weight", 0.0, 1.0, 0.1, 0.01, key="custom_weight")
        custom_tags = st.text_input("Tags (comma-separated)", key="custom_tags")
        submitted = st.form_submit_button("Add criterion")
        if submitted:
            if not custom_question.strip():
                st.warning("Please provide a question for the custom criterion.")
            else:
                cid = slugify(custom_name or custom_question[:40])
                new_c = {
                    "id": cid,
                    "name": custom_name or custom_question[:40],
                    "question": custom_question.strip(),
                    "rationale": "HR-added custom criterion",
                    "expected_evidence": [],
                    "leniency_note": "",
                    "weight": float(custom_weight),
                    "fail_examples": [],
                    "tags": [t.strip() for t in (custom_tags.split(",") if custom_tags else []) if t.strip()],
                }
                # Append to criteria_doc in session
                criteria_doc["criteria"].append(new_c)
                # Update selection/weights
                st.session_state["criteria_selection"][cid] = True
                st.session_state["criteria_weights"][cid] = float(custom_weight)
                st.success(f"Added custom criterion '{cid}'.")

    if st.button("Finalize criteria"):
        # Build final doc with selected criteria and updated weights
        selected = []
        for c in criteria_doc["criteria"]:
            if st.session_state["criteria_selection"].get(c["id"], False):
                c2 = dict(c)
                c2["weight"] = float(st.session_state["criteria_weights"][c["id"]])
                selected.append(c2)
        if not selected:
            st.error("Please select at least one criterion before finalizing.")
        else:
            # Normalize weights to ~1
            total_w = sum(c["weight"] for c in selected) or 1.0
            for c in selected:
                c["weight"] = round(c["weight"] / total_w, 4)
            final_doc = {
                "role_summary": criteria_doc.get("role_summary", ""),
                "seniority": criteria_doc.get("seniority", "intern"),
                "total_criteria": len(selected),
                "criteria": selected,
            }
            st.session_state["final_criteria_doc"] = final_doc
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            path = os.path.join(DATA_DIR, f"criteria_final_{ts}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(final_doc, f, indent=2, ensure_ascii=False)
            st.success(f"Finalized criteria saved to data/ as criteria_final_{ts}.json")
            st.download_button("Download finalized_criteria.json", json.dumps(final_doc, indent=2, ensure_ascii=False).encode("utf-8"), "finalized_criteria.json", "application/json")

    # Show recent saved criteria files
    with st.expander("Previously saved criteria in data/ (download)"):
        try:
            files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("criteria_final_") and f.endswith(".json")])
            for fname in files[-10:]:
                fpath = os.path.join(DATA_DIR, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    data = f.read().encode("utf-8")
                st.download_button(f"Download {fname}", data, file_name=fname, mime="application/json", key=f"dl_{fname}")
        except Exception as e:
            st.caption(f"(no saved files or error: {e})")

# Step 2: Upload resumes & run analysis → show simple table
st.header("Step 2 — Upload resumes and run analysis")
resume_files = st.file_uploader("Upload resumes (PDF/DOCX/TXT)", type=["pdf","docx","txt"], accept_multiple_files=True)
if st.button("Run analysis"):
    if not criteria_doc:
        st.error("Please generate criteria first (Step 1).")
    elif not resume_files:
        st.error("Please upload at least one resume.")
    elif not OPENAI_API_KEY:
        st.error("Server is missing OPENAI_API_KEY. Please contact the admin.")
    else:
        resumes_payload = []
        for f in resume_files:
            try:
                text = extract_text_from_upload(f)
            except Exception as e:
                st.warning(f"Could not read {f.name}: {e}")
                continue
            resumes_payload.append({"id": f.name, "text": text[:20000]})
        if not resumes_payload:
            st.error("No readable resumes.")
        else:
            try:
                matcher = OpenAIResumeMatcher(
                    api_key=OPENAI_API_KEY, model_name=OPENAI_MODEL_MATCH, max_reasons=3
                )
                # Use finalized criteria if present; else original
                crit_doc = final_criteria_doc or criteria_doc
                crit_list = crit_doc["criteria"]
                q_for_model = [{"id": c["id"], "question": c["question"]} for c in crit_list]
                result = matcher.run(
                    jd=jd_input or "(JD not provided)",
                    hr=hr_input or "(none provided)",
                    questions=q_for_model,
                    resumes=resumes_payload
                )
            except Exception as e:
                st.error(f"Matching failed: {e}")
                result = None

            if result:
                rows = []
                # Build helper maps for weights
                weight_by_id = {c["id"]: float(c.get("weight", 0.0)) for c in (final_criteria_doc or criteria_doc)["criteria"]}
                total_weight = sum(weight_by_id.values()) or 1.0
                for r in result.get("results", []):
                    rid = r.get("resume_id","")
                    yes = int(r.get("yes_count", 0))
                    no = int(r.get("no_count", 0))
                    # Compute weighted yes score
                    w_yes = 0.0
                    for ans in r.get("answers", []):
                        cid = ans.get("criterion_id")
                        if ans.get("answer") == "yes" and cid in weight_by_id:
                            w_yes += weight_by_id[cid]
                    w_yes = round(w_yes / total_weight, 4)
                    # Grouping logic
                    if w_yes >= 0.75:
                        group = "Strongly Consider"
                    elif w_yes >= 0.5:
                        group = "Potential Fit"
                    else:
                        group = "Rejected"
                    rel = "Relevant" if r.get("majority_pass", False) else "Not Relevant"
                    rows.append({"Resume": rid, "Yes": yes, "No": no, "WeightedScore": w_yes, "Group": group, "Relevance": rel})

                if rows:
                    SUMMARY_COLS_EXT = ["Resume", "Yes", "No", "WeightedScore", "Group", "Relevance"]
                    df = pd.DataFrame(rows, columns=SUMMARY_COLS_EXT)
                    st.subheader("Results")
                    st.dataframe(df, use_container_width=True)

                    csv = df.to_csv(index=False).encode("utf-8")
                    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                    st.download_button(f"Download results_{ts}.csv", csv, f"results_{ts}.csv", "text/csv")

                    # Save full JSON to data/
                    try:
                        full_path = os.path.join(DATA_DIR, f"results_{ts}.json")
                        with open(full_path, "w", encoding="utf-8") as f:
                            json.dump(result, f, indent=2, ensure_ascii=False)
                        st.caption(f"Saved detailed results to data/results_{ts}.json")
                    except Exception as e:
                        st.caption(f"(could not save results json: {e})")

                    # Keep detailed LLM answers hidden unless HR explicitly asks
                    if st.checkbox("Show detailed answers (per question)", value=False):
                        st.subheader("Detailed answers")
                        st.json(result)

                    st.markdown("\n---\n")
                    st.subheader("Per-resume insights and charts")
                    crit_map = {c["id"]: c for c in (final_criteria_doc or criteria_doc)["criteria"]}
                    for r in result.get("results", []):
                        rid = r.get("resume_id", "")
                        yes = int(r.get("yes_count", 0))
                        no = int(r.get("no_count", 0))
                        # Chart: simple bar for Yes/No
                        chart_df = pd.DataFrame({"Answer": ["Yes", "No"], "Count": [yes, no]})
                        bar = alt.Chart(chart_df).mark_bar().encode(x="Answer", y="Count", tooltip=["Answer","Count"]).properties(width=300, height=200)
                        with st.expander(f"{rid} — details"):
                            st.altair_chart(bar, use_container_width=False)
                            # Explanation: list key positives/negatives
                            pos, neg = [], []
                            for ans in r.get("answers", []):
                                cid = ans.get("criterion_id")
                                question = ans.get("question")
                                reasons = "; ".join(ans.get("reasons", [])[:3])
                                row = {
                                    "Criterion": cid or "?",
                                    "Question": question,
                                    "Answer": ans.get("answer"),
                                    "Weight": weight_by_id.get(cid, 0.0),
                                    "Reasons": reasons,
                                }
                                if ans.get("answer") == "yes":
                                    pos.append(row)
                                else:
                                    neg.append(row)
                            st.markdown("**Top strengths (criteria matched):**")
                            if pos:
                                pos_df = pd.DataFrame(pos).sort_values("Weight", ascending=False)
                                st.dataframe(pos_df, use_container_width=True)
                            else:
                                st.write("No matched criteria.")
                            st.markdown("**Gaps (criteria not matched):**")
                            if neg:
                                neg_df = pd.DataFrame(neg).sort_values("Weight", ascending=False)
                                st.dataframe(neg_df, use_container_width=True)
                            else:
                                st.write("No failed criteria.")

                    # Provide quick downloads of last few saved results
                    with st.expander("Previously saved results in data/ (download)"):
                        try:
                            files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("results_") and f.endswith(".json")])
                            for fname in files[-10:]:
                                fpath = os.path.join(DATA_DIR, fname)
                                with open(fpath, "r", encoding="utf-8") as f:
                                    data = f.read().encode("utf-8")
                                st.download_button(f"Download {fname}", data, file_name=fname, mime="application/json", key=f"dl_{fname}")
                        except Exception as e:
                            st.caption(f"(no saved files or error: {e})")
