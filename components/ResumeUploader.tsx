
import React, { useState, useCallback, useRef } from 'react';
import { FileIcon } from './icons/FileIcon';
import { UploadIcon } from './icons/UploadIcon';

interface ResumeUploaderProps {
  onFilesChange: (files: File[]) => void;
  disabled: boolean;
}

export default function ResumeUploader({ onFilesChange, disabled }: ResumeUploaderProps) {
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      const newFiles = Array.from(event.target.files as FileList) as File[];
      setUploadedFiles(newFiles);
      onFilesChange(newFiles);
    }
  }, [onFilesChange]);

  const handleDragOver = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
  };

  const handleDrop = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    if (event.dataTransfer.files) {
      const newFiles = Array.from(event.dataTransfer.files as FileList) as File[];
      setUploadedFiles(newFiles);
      onFilesChange(newFiles);
      if (fileInputRef.current) {
        fileInputRef.current.files = event.dataTransfer.files;
      }
    }
  };

  return (
    <div>
      <label
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        htmlFor="resume-upload"
        className={`flex flex-col items-center justify-center w-full h-48 border-2 border-slate-300 border-dashed rounded-lg cursor-pointer bg-slate-50 hover:bg-slate-100 transition-colors duration-200 ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
      >
        <div className="flex flex-col items-center justify-center pt-5 pb-6">
          <UploadIcon className="w-10 h-10 mb-3 text-slate-400" />
          <p className="mb-2 text-sm text-slate-500">
            <span className="font-semibold">Click to upload</span> or drag and drop
          </p>
          <p className="text-xs text-slate-500">Multiple files accepted: PDF, DOCX, TXT</p>
        </div>
        <input
          id="resume-upload"
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
          multiple
          className="hidden"
          onChange={handleFileChange}
          disabled={disabled}
        />
      </label>
      {uploadedFiles.length > 0 && (
        <div className="mt-4">
          <h4 className="font-semibold text-slate-600">Selected files:</h4>
          <ul className="mt-2 space-y-2">
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