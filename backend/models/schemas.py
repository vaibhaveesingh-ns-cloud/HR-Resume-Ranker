from pydantic import BaseModel
from typing import List, Optional

class Candidate(BaseModel):
    id: str
    name: str
    github_url: str
    group: str
    score: int
    python_proficiency: bool
    ai_library_experience: bool
    ml_exposure: bool
    ai_project_evidence: bool
    justification: str
    file_name: str

class RejectedCandidate(BaseModel):
    id: str
    name: str
    reason: str
    file_name: str

class RankingResponse(BaseModel):
    ranked_candidates: List[Candidate]
    rejected_candidates: List[RejectedCandidate]
    total_processed: int

class JobDescriptionRequest(BaseModel):
    job_description: str
