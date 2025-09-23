from typing import List, Literal
from pydantic import BaseModel


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
