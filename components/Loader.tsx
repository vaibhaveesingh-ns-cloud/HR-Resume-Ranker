
import React from 'react';

export default function Loader() {
  return (
    <div className="flex flex-col items-center justify-center my-12">
        <div className="w-16 h-16 border-4 border-t-4 border-slate-200 border-t-indigo-600 rounded-full animate-spin"></div>
        <p className="mt-4 text-slate-600">Analyzing candidates, please wait...</p>
    </div>
  );
}
