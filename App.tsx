
import React, { useState, useCallback, useMemo } from 'react';
import Header from './components/Header';
import JobDescriptionInput from './components/JobDescriptionInput';
import ResumeUploader from './components/ResumeUploader';
import ResultsDisplay from './components/ResultsDisplay';
import Loader from './components/Loader';
import { rankResumes } from './services/geminiService';
import type { Candidate, RejectedCandidate } from './types';

export default function App() {
  const [jobDescription, setJobDescription] = useState('');
  const [resumeFiles, setResumeFiles] = useState<File[]>([]);
  const [rankedCandidates, setRankedCandidates] = useState<Candidate[]>([]);
  const [rejectedCandidates, setRejectedCandidates] = useState<RejectedCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRankClick = useCallback(async () => {
    if (!jobDescription.trim() || resumeFiles.length === 0) {
      setError('Please provide a job description and a zip file with resumes.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setRankedCandidates([]);
    setRejectedCandidates([]);

    try {
      const { ranked, rejected } = await rankResumes(jobDescription, resumeFiles);
      setRankedCandidates(ranked);
      setRejectedCandidates(rejected);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'An unknown error occurred during analysis.');
    } finally {
      setIsLoading(false);
    }
  }, [jobDescription, resumeFiles]);

  const isButtonDisabled = useMemo(() => {
    return isLoading || !jobDescription.trim() || resumeFiles.length === 0;
  }, [isLoading, jobDescription, resumeFiles.length]);
  
  const hasResults = useMemo(() => rankedCandidates.length > 0 || rejectedCandidates.length > 0, [rankedCandidates, rejectedCandidates]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans">
      <Header />
      <main className="max-w-4xl mx-auto p-4 md:p-8">
        <div className="space-y-8">
          <div className="p-8 bg-white rounded-2xl shadow-lg border border-slate-200">
            <h2 className="text-2xl font-bold text-slate-700 mb-1">Step 1: Provide Job Description</h2>
            <p className="text-slate-500 mb-6">Paste the full job description below.</p>
            <JobDescriptionInput value={jobDescription} onChange={setJobDescription} disabled={isLoading} />
          </div>

          <div className="p-8 bg-white rounded-2xl shadow-lg border border-slate-200">
            <h2 className="text-2xl font-bold text-slate-700 mb-1">Step 2: Upload Resumes</h2>
            <p className="text-slate-500 mb-6">Upload a single <code className="bg-slate-100 text-slate-600 px-1 py-0.5 rounded">.zip</code> file containing all candidate resumes in PDF format.</p>
            <ResumeUploader onFilesChange={setResumeFiles} disabled={isLoading} />
          </div>

          <div className="flex flex-col items-center">
            <button
              onClick={handleRankClick}
              disabled={isButtonDisabled}
              className="w-full md:w-auto px-12 py-4 bg-indigo-600 text-white font-bold text-lg rounded-xl shadow-md hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-all duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              {isLoading ? 'Analyzing...' : 'Rank Candidates'}
            </button>
            {error && <p className="text-red-500 mt-4 text-center">{error}</p>}
          </div>
        </div>

        {isLoading && <Loader />}

        {!isLoading && hasResults && (
          <div className="mt-12">
            <ResultsDisplay rankedCandidates={rankedCandidates} rejectedCandidates={rejectedCandidates} />
          </div>
        )}
      </main>
      <footer className="text-center py-6 text-slate-500 text-sm">
        <p>Powered by Gemini API</p>
      </footer>
    </div>
  );
}