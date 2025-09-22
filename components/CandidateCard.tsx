
import React from 'react';
import type { Candidate } from '../types';
import { GithubIcon } from './icons/GithubIcon';
import { UserIcon } from './icons/UserIcon';

interface CandidateCardProps {
  candidate: Candidate;
  rank: number;
}

const getRankColor = (rank: number) => {
  if (rank === 1) return 'border-amber-400 bg-amber-50';
  if (rank === 2) return 'border-slate-400 bg-slate-100';
  if (rank === 3) return 'border-orange-400 bg-orange-50';
  return 'border-slate-200 bg-white';
};

const getScoreColor = (score: number) => {
    if (score >= 90) return 'bg-green-500';
    if (score >= 75) return 'bg-lime-500';
    if (score >= 60) return 'bg-yellow-500';
    return 'bg-orange-500';
}

export default function CandidateCard({ candidate, rank }: CandidateCardProps) {
  const rankColorClass = getRankColor(rank);

  return (
    <div className={`p-6 rounded-2xl border-2 shadow-md transition-transform hover:scale-[1.01] ${rankColorClass}`}>
      <div className="flex flex-col md:flex-row md:items-start gap-6">
        <div className="flex items-center gap-4">
            <div className="text-3xl font-bold text-slate-500 w-10 text-center">{rank}</div>
            <div className={`w-20 h-20 rounded-full flex-shrink-0 flex items-center justify-center ${getScoreColor(candidate.score)} text-white shadow-inner`}>
                <div className="text-center">
                    <span className="text-3xl font-bold">{candidate.score}</span>
                    <span className="text-xs block -mt-1">/ 100</span>
                </div>
            </div>
        </div>

        <div className="flex-grow">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="text-2xl font-bold text-slate-800">{candidate.name}</h3>
              <p className="text-sm text-slate-400" title={candidate.fileName}>{candidate.fileName}</p>
            </div>
            <a
              href={candidate.githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-800 font-semibold transition-colors"
            >
              <GithubIcon className="w-5 h-5" />
              <span>GitHub Profile</span>
            </a>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-200">
            <h4 className="font-semibold text-slate-600 mb-2">AI Justification:</h4>
            <p className="text-slate-700 whitespace-pre-wrap text-sm">{candidate.justification}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
