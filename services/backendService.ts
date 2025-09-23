// Simple API client to call FastAPI backend

export interface GenerateCriteriaRequest {
  jd: string;
  hr?: string;
  n: number;
  seniority: 'intern' | 'junior' | 'mid' | 'senior' | 'lead' | 'principal';
}

export interface Criterion {
  id: string;
  name: string;
  question: string;
  rationale: string;
  expected_evidence: string[];
  leniency_note: string;
  weight: number;
  fail_examples: string[];
  tags: string[];
}

export interface QuestionsDoc {
  role_summary: string;
  seniority: GenerateCriteriaRequest['seniority'];
  total_criteria: number;
  criteria: Criterion[];
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

export async function generateCriteria(req: GenerateCriteriaRequest): Promise<QuestionsDoc> {
  const res = await fetch(`${API_BASE}/criteria/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Failed to generate criteria: ${res.status}`);
  }
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data as QuestionsDoc;
}

export interface AnalyzeResponse {
  results: Array<{
    resume_id: string;
    answers: Array<{
      criterion_id: string;
      question: string;
      answer: 'yes' | 'no';
      reasons: string[];
    }>;
    yes_count: number;
    no_count: number;
    majority_pass: boolean;
  }>;
  timestamp: string;
}

export async function analyzeResumes(params: {
  jd: string;
  hr: string;
  criteriaDoc: QuestionsDoc;
  files: File[];
}): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append('jd', params.jd || '');
  form.append('hr', params.hr || '');
  form.append('criteria_json', JSON.stringify(params.criteriaDoc));
  for (const f of params.files) {
    form.append('resumes', f, f.name);
  }

  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Failed to analyze: ${res.status}`);
  }
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data as AnalyzeResponse;
}
