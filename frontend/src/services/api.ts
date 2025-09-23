import axios from 'axios';
import { RankingResponse } from '../types';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes timeout for long-running operations
});

export const rankResumes = async (
  jobDescription: string,
  resumeFile: File,
  onProgress?: (progress: number) => void
): Promise<RankingResponse> => {
  const formData = new FormData();
  formData.append('job_description', jobDescription);
  formData.append('resume_file', resumeFile);

  try {
    const response = await api.post('/api/rank-resumes', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to rank resumes');
    }
    throw new Error('An unexpected error occurred');
  }
};

export const healthCheck = async (): Promise<{ status: string; service: string }> => {
  const response = await api.get('/health');
  return response.data;
};
