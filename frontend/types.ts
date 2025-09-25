
export interface Candidate {
  id: string;
  name: string;
  githubUrl: string;
  group: string;
  score: number;
  pythonProficiency: boolean;
  aiLibraryExperience: boolean;
  mlExposure: boolean;
  aiProjectEvidence: boolean;
  justification: string;
  fileName: string;
}

export interface RejectedCandidate {
  id: string;
  name: string;
  reason: string;
  fileName: string;
}
