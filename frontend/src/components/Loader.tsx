import React from 'react';

export default function Loader() {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-indigo-600 mb-4"></div>
      <p className="text-slate-600 text-lg font-medium">Processing resumes...</p>
      <p className="text-slate-500 text-sm mt-2">This may take a few minutes</p>
    </div>
  );
}
