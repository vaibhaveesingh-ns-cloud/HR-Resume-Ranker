import React from 'react';

export default function Header() {
  return (
    <header className="bg-white shadow-sm border-b border-slate-200">
      <div className="max-w-4xl mx-auto px-4 py-6 md:px-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-slate-800 mb-2">
            HR Resume Ranker
          </h1>
          <p className="text-lg text-slate-600">
            AI-powered candidate evaluation and ranking system
          </p>
        </div>
      </div>
    </header>
  );
}
