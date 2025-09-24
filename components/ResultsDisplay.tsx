
import React from 'react';
import type { Candidate, RejectedCandidate } from '../types';
import CandidateCard from './CandidateCard';
import { UserIcon } from './icons/UserIcon';


interface ResultsDisplayProps {
  rankedCandidates: Candidate[];
  rejectedCandidates: RejectedCandidate[];
}

export default function ResultsDisplay({ rankedCandidates, rejectedCandidates }: ResultsDisplayProps) {
  return (
    <section className="space-y-12">
      {rankedCandidates.length > 0 && (
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-800 mb-6">Top Candidates</h2>
          <div className="space-y-4">
            {rankedCandidates.map((candidate, index) => (
              <CandidateCard key={candidate.id} candidate={candidate} rank={index + 1} />
            ))}
          </div>
        </div>
      )}

      {rejectedCandidates.length > 0 && (
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-800 mb-6">Not a Fit</h2>
           <div className="space-y-3">
            {rejectedCandidates.map((candidate) => (
              <div key={candidate.id} className="p-4 bg-white border border-slate-200 rounded-lg flex items-center shadow-sm">
                <div className="p-2 bg-red-100 rounded-full mr-4">
                    <UserIcon className="w-6 h-6 text-red-500" />
                </div>
                <div className="flex-grow">
                    <p className="font-bold text-slate-800">{candidate.name || 'Unknown Candidate'}</p>
                    <p className="text-sm text-red-600">{candidate.reason}</p>
                </div>
                <p className="text-xs text-slate-400 truncate ml-4" title={candidate.fileName}>{candidate.fileName}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
