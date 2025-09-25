import React, { useCallback, useRef, useState } from 'react';
import { FileIcon } from './icons/FileIcon';
import { UploadIcon } from './icons/UploadIcon';

export default function MultiResumeUploader({
  onFilesChange,
  disabled,
}: {
  onFilesChange: (files: File[]) => void;
  disabled: boolean;
}) {
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setUploadedFiles(files);
      onFilesChange(files);
    }
  }, [onFilesChange]);

  const handleDragOver = (e: React.DragEvent<HTMLLabelElement>) => e.preventDefault();
  const handleDrop = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      const files = Array.from(e.dataTransfer.files);
      setUploadedFiles(files);
      onFilesChange(files);
      if (inputRef.current) inputRef.current.files = e.dataTransfer.files;
    }
  };

  return (
    <div>
      <label
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        htmlFor="multi-resume-upload"
        className={`flex flex-col items-center justify-center w-full h-48 border-2 border-slate-300 border-dashed rounded-lg cursor-pointer bg-slate-50 hover:bg-slate-100 transition-colors duration-200 ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
      >
        <div className="flex flex-col items-center justify-center pt-5 pb-6">
          <UploadIcon className="w-10 h-10 mb-3 text-slate-400" />
          <p className="mb-2 text-sm text-slate-500">
            <span className="font-semibold">Click to upload</span> or drag and drop
          </p>
          <p className="text-xs text-slate-500">PDF, DOCX, or TXT (multiple allowed)</p>
        </div>
        <input
          id="multi-resume-upload"
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          multiple
          className="hidden"
          onChange={handleFileChange}
          disabled={disabled}
        />
      </label>
      {uploadedFiles.length > 0 && (
        <div className="mt-4">
          <h4 className="font-semibold text-slate-600">Selected files:</h4>
          <ul className="mt-2 space-y-2 max-h-40 overflow-auto pr-1">
            {uploadedFiles.map((file) => (
              <li key={file.name} className="flex items-center text-sm text-slate-700 bg-slate-100 rounded-md p-2">
                <FileIcon className="w-5 h-5 mr-2 text-slate-500 flex-shrink-0" />
                <span className="truncate">{file.name}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
