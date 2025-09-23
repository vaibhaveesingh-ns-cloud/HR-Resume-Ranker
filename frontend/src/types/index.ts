export interface Candidate {
  id: string;
  name: string;
  github_url: string;
  group: string;
  score: number;
  python_proficiency: boolean;
  ai_library_experience: boolean;
  ml_exposure: boolean;
  ai_project_evidence: boolean;
  justification: string;
  file_name: string;
}

export interface RejectedCandidate {
  id: string;
  name: string;
  reason: string;
  file_name: string;
}

export interface RankingResponse {
  ranked_candidates: Candidate[];
  rejected_candidates: RejectedCandidate[];
  total_processed: number;
}
