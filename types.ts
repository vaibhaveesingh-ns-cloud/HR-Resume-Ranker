
export interface Candidate {
  id: string;
  name: string;
  githubUrl: string;
  score: number;
  justification: string;
  fileName: string;
}

export interface RejectedCandidate {
  id: string;
  name: string;
  reason: string;
  fileName: string;
}
