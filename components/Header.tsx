
import React from 'react';

export default function Header() {
  return (
    <header className="bg-white/80 backdrop-blur-lg border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-4xl mx-auto py-4 px-4 md:px-8">
        <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">
          HR AI Resume Ranker
        </h1>
        <p className="text-slate-500 mt-1">
          Streamline your hiring process with AI-powered analysis.
        </p>
      </div>
    </header>
  );
}
