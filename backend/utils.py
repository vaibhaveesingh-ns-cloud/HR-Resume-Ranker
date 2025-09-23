import os
import re
import json
import tempfile
from typing import List

import httpx
from dotenv import load_dotenv
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document as DocxDocument


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
    r = httpx.post(url, headers=headers, json=body, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
