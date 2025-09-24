
import React from 'react';

interface JobDescriptionInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}

export default function JobDescriptionInput({ value, onChange, disabled }: JobDescriptionInputProps) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      placeholder="e.g., Senior React Developer with experience in TypeScript and Next.js..."
      className="w-full h-48 p-4 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors duration-200 ease-in-out disabled:bg-slate-100"
    />
  );
}
