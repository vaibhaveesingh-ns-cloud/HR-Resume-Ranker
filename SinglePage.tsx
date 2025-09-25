import React, { useCallback, useMemo, useState } from 'react';
import Header from './components/Header';
import JobDescriptionInput from './components/JobDescriptionInput';
import ResumeUploader from './components/ResumeUploader';
import Loader from './components/Loader';
import { generateCriteria, analyzeResumes, type QuestionsDoc, type AnalyzeResponse } from './services/backendService';

export default function SinglePage() {
  const [jobDescription, setJobDescription] = useState('');
  const [hrNotes, setHrNotes] = useState('');
  const [resumeFiles, setResumeFiles] = useState<File[]>([]);
  const [criteriaDoc, setCriteriaDoc] = useState<QuestionsDoc | null>(null);
  const [seniority, setSeniority] = useState<QuestionsDoc['seniority']>('intern');
  const [customSeniority, setCustomSeniority] = useState('');
  const [criteriaCount, setCriteriaCount] = useState<number>(8);
  const [requireGithub, setRequireGithub] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [expandedResumeId, setExpandedResumeId] = useState<string | null>(null);
  // Track total resumes during an analysis run so we can display progress info
  const [totalDuringAnalysis, setTotalDuringAnalysis] = useState<number | null>(null);
  // Group filtering state
  const [visibleGroups, setVisibleGroups] = useState<Set<string>>(new Set(['strongly_consider', 'potential_fit', 'rejected']));

  // Unique results (dedupe by resume_id), then filter by selected groups
  const filteredResults = useMemo(() => {
    if (!analysis) return [] as AnalyzeResponse['results'];
    const seen = new Set<string>();
    const unique: AnalyzeResponse['results'] = [];
    for (const r of analysis.results) {
      if (seen.has(r.resume_id)) continue;
      seen.add(r.resume_id);
      unique.push(r);
    }
    return unique.filter(r => visibleGroups.has(r.group));
  }, [analysis, visibleGroups]);

  // Download criteria as JSON
  const handleDownloadCriteria = useCallback(() => {
    if (!criteriaDoc) return;
    
    const dataStr = JSON.stringify(criteriaDoc, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `criteria_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [criteriaDoc]);

  // Upload criteria from JSON file
  const handleUploadCriteria = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const parsed = JSON.parse(content);
        
        // Validate basic structure
        if (parsed.criteria && Array.isArray(parsed.criteria)) {
          setCriteriaDoc(parsed as QuestionsDoc);
          setError(null);
        } else {
          setError('Invalid criteria file format');
        }
      } catch (err) {
        setError('Failed to parse criteria file');
      }
    };
    reader.readAsText(file);
    
    // Reset input
    event.target.value = '';
  }, []);

  // Download filtered results as CSV
  const handleDownloadCSV = useCallback(() => {
    if (!filteredResults.length) return;
    
    const headers = ['Resume', 'Group', 'GitHub', 'LinkedIn', 'Criteria Met (%)', 'Yes Count', 'No Count', 'Group Reason'];
    const rows = filteredResults.map(r => {
      const total = r.yes_count + r.no_count;
      const pct = total > 0 ? Math.round((r.yes_count / total) * 100) : 0;
      return [
        r.resume_id,
        r.group === 'strongly_consider' ? 'Strongly Consider' : r.group === 'potential_fit' ? 'Potential Fit' : 'Rejected',
        r.has_github ? 'Yes' : 'No',
        (r.has_github && r.has_linkedin) ? 'Yes' : 'No',
        `${pct}%`,
        r.yes_count.toString(),
        r.no_count.toString(),
        r.group_reason
      ];
    });
    
    const csvContent = [headers, ...rows].map(row => 
      row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(',')
    ).join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `resume_analysis_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [filteredResults]);

  // Group counts computed from unique results
  const groupCounts = useMemo(() => {
    if (!analysis) return { strongly_consider: 0, potential_fit: 0, rejected: 0 } as Record<string, number>;
    const seen = new Set<string>();
    const counts: Record<string, number> = { strongly_consider: 0, potential_fit: 0, rejected: 0 };
    for (const r of analysis.results) {
      if (seen.has(r.resume_id)) continue;
      seen.add(r.resume_id);
      counts[r.group] = (counts[r.group] || 0) + 1;
    }
    return counts;
  }, [analysis]);

  const handleGenerateCriteria = useCallback(async () => {
    if (!jobDescription.trim()) {
      setError('Please provide a job description before generating criteria.');
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      const doc = await generateCriteria({ 
        jd: jobDescription, 
        hr: hrNotes, 
        n: criteriaCount, 
        seniority: customSeniority ? (customSeniority as any) : seniority 
      });
      setCriteriaDoc(doc);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to generate criteria');
    } finally {
      setIsLoading(false);
    }
  }, [jobDescription, hrNotes, criteriaCount, seniority, customSeniority]);

  const handleAnalyze = useCallback(async () => {
    if (!jobDescription.trim() || resumeFiles.length === 0) {
      setError('Please provide a job description and upload resumes (PDF/DOCX/TXT).');
      return;
    }
    if (!criteriaDoc) {
      setError('Please generate or provide criteria first.');
      return;
    }
    setIsLoading(true);
    setTotalDuringAnalysis(resumeFiles.length);
    setError(null);
    setAnalysis(null);
    setExpandedResumeId(null);
    try {
      const resp = await analyzeResumes({ jd: jobDescription, hr: hrNotes, criteriaDoc, files: resumeFiles, requireGithub });
      setAnalysis(resp);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to analyze resumes');
    } finally {
      setIsLoading(false);
    }
  }, [jobDescription, hrNotes, criteriaDoc, resumeFiles, requireGithub]);

  const isAnalyzeDisabled = useMemo(() => {
    return isLoading || !jobDescription.trim() || resumeFiles.length === 0 || !criteriaDoc;
  }, [isLoading, jobDescription, resumeFiles.length, criteriaDoc]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans">
      <Header />
      <main className="max-w-5xl mx-auto p-4 md:p-8">
        <div className="space-y-8">
          <div className="p-8 bg-white rounded-2xl shadow-lg border border-slate-200">
            <h2 className="text-2xl font-bold text-slate-700 mb-1">Step 1: Provide Job Description & HR Notes</h2>
            <p className="text-slate-500 mb-6">Paste the full job description and optional HR notes. These guide the criteria and evaluation.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="font-semibold text-slate-700 mb-2">Job Description</h3>
                <JobDescriptionInput value={jobDescription} onChange={setJobDescription} disabled={isLoading} />
              </div>
              <div>
                <h3 className="font-semibold text-slate-700 mb-2">HR Notes</h3>
                <textarea
                  value={hrNotes}
                  onChange={(e) => setHrNotes(e.target.value)}
                  disabled={isLoading}
                  placeholder="Any preferences, culture fits, must-haves or nice-to-haves, etc."
                  className="w-full h-48 p-4 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors duration-200 ease-in-out disabled:bg-slate-100"
                />
              </div>
            </div>
          </div>

          <div className="p-8 bg-white rounded-2xl shadow-lg border border-slate-200">
            <h2 className="text-2xl font-bold text-slate-700 mb-1">Step 2: Criteria & Resume Upload</h2>
            <p className="text-slate-500 mb-6">Generate criteria, review/edit checklist, then upload resumes (multiple PDF/DOCX/TXT). GitHub requirement can be toggled for non-tech roles.</p>
            <div className="flex flex-col gap-6">
              <div className="flex flex-wrap items-end gap-4">
                <div className="flex gap-2">
                  <div>
                    <label className="block text-sm text-slate-600 mb-1">Seniority</label>
                    <select 
                      className="border rounded px-3 py-2" 
                      value={customSeniority ? 'custom' : seniority} 
                      onChange={(e) => {
                        if (e.target.value === 'custom') {
                          setCustomSeniority('Custom');
                        } else {
                          setSeniority(e.target.value as any);
                          setCustomSeniority('');
                        }
                      }} 
                      disabled={isLoading}
                    >
                      <option value="intern">Intern</option>
                      <option value="junior">Junior</option>
                      <option value="mid">Mid</option>
                      <option value="senior">Senior</option>
                      <option value="lead">Lead</option>
                      <option value="principal">Principal</option>
                      <option value="custom">Custom...</option>
                    </select>
                  </div>
                  {customSeniority && (
                    <div>
                      <label className="block text-sm text-slate-600 mb-1">Custom Role</label>
                      <input 
                        type="text"
                        className="border rounded px-3 py-2 w-32"
                        value={customSeniority}
                        onChange={(e) => setCustomSeniority(e.target.value)}
                        placeholder="e.g., VP, CTO"
                        disabled={isLoading}
                      />
                    </div>
                  )}
                </div>
                <div>
                  <label className="block text-sm text-slate-600 mb-1"># Criteria</label>
                  <input type="number" min={3} max={15} className="border rounded px-3 py-2 w-28" value={criteriaCount} onChange={(e) => setCriteriaCount(Number(e.target.value))} disabled={isLoading} />
                </div>
                <button onClick={handleGenerateCriteria} disabled={isLoading || !jobDescription.trim()} className="px-4 py-2 bg-indigo-600 text-white rounded shadow hover:bg-indigo-700 disabled:bg-slate-300">Generate Criteria</button>
                <div className="flex gap-2">
                  <label className="px-3 py-2 bg-green-600 text-white rounded shadow hover:bg-green-700 cursor-pointer text-sm">
                    📁 Upload Criteria
                    <input type="file" accept=".json" onChange={handleUploadCriteria} className="hidden" disabled={isLoading} />
                  </label>
                  {criteriaDoc && (
                    <button onClick={handleDownloadCriteria} className="px-3 py-2 bg-blue-600 text-white rounded shadow hover:bg-blue-700 text-sm" disabled={isLoading}>
                      💾 Download Criteria
                    </button>
                  )}
                </div>
                <label className="inline-flex items-center gap-2 ml-auto select-none">
                  <input type="checkbox" className="w-4 h-4" checked={requireGithub} onChange={(e) => setRequireGithub(e.target.checked)} disabled={isLoading} />
                  <span className="text-sm text-slate-700">Require GitHub (toggle off for non-tech)</span>
                </label>
              </div>

              {criteriaDoc && (
                <div className="border rounded-xl p-4 bg-slate-50">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-700">Criteria Checklist</h3>
                    <span className="text-xs text-slate-500">Edit questions directly. Weights are ignored.</span>
                  </div>
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
                    {criteriaDoc.criteria.map((c, idx) => (
                      <div key={c.id} className="bg-white border rounded-lg p-3">
                        <input
                          className="w-full font-semibold text-slate-800 mb-1 outline-none"
                          value={c.name}
                          onChange={(e) => {
                            const next = { ...criteriaDoc } as QuestionsDoc;
                            next.criteria = next.criteria.map((cc, i) => i === idx ? { ...cc, name: e.target.value } : cc);
                            setCriteriaDoc(next);
                          }}
                        />
                        <textarea
                          className="w-full text-sm text-slate-700 outline-none"
                          value={c.question}
                          onChange={(e) => {
                            const next = { ...criteriaDoc } as QuestionsDoc;
                            next.criteria = next.criteria.map((cc, i) => i === idx ? { ...cc, question: e.target.value } : cc);
                            setCriteriaDoc(next);
                          }}
                        />
                        <div className="mt-2 flex justify-end gap-2">
                          <button
                            className="text-xs text-red-600 hover:underline"
                            onClick={() => {
                              const next = { ...criteriaDoc } as QuestionsDoc;
                              next.criteria = next.criteria.filter((_, i) => i !== idx);
                              next.total_criteria = next.criteria.length;
                              setCriteriaDoc(next);
                            }}
                          >Remove</button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3">
                    <button
                      className="text-sm px-3 py-1 border rounded hover:bg-slate-100"
                      onClick={() => {
                        if (!criteriaDoc) return;
                        const next = { ...criteriaDoc } as QuestionsDoc;
                        const newId = `custom_${Date.now()}`;
                        next.criteria = [
                          ...next.criteria,
                          { id: newId, name: 'Custom criterion', question: 'Does the resume show ...?', rationale: '', expected_evidence: [], leniency_note: '', weight: 0, fail_examples: [], tags: [] }
                        ];
                        next.total_criteria = next.criteria.length;
                        setCriteriaDoc(next);
                      }}
                    >Add criterion</button>
                  </div>
                </div>
              )}

              <div>
                <div className="border rounded-lg p-4 bg-slate-50">
                  <h3 className="font-semibold text-slate-700 mb-3">Resume Management</h3>
                  <div className="flex gap-3 items-center">
                    {resumeFiles.length > 0 ? (
                      <>
                        <div className="flex-1">
                          <label className="block text-sm text-slate-600 mb-1">
                            Uploaded Resumes ({resumeFiles.length})
                          </label>
                          <select className="w-full border rounded px-3 py-2 bg-white" disabled={isLoading}>
                            <option value="">View uploaded files...</option>
                            {resumeFiles.map((file, idx) => (
                              <option key={idx} value={file.name}>{file.name}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-sm text-slate-600 mb-1">Add More</label>
                          <label className="px-4 py-2 bg-indigo-600 text-white rounded shadow hover:bg-indigo-700 cursor-pointer">
                            + Add Files
                            <input 
                              type="file" 
                              multiple 
                              accept=".pdf,.docx,.txt" 
                              onChange={(e) => {
                                const newFiles = Array.from(e.target.files || []);
                                if (newFiles.length > 0) {
                                  setResumeFiles((prev: File[]) => {
                                    const existing = new Set(prev.map(f => f.name));
                                    const unique = newFiles.filter(f => !existing.has(f.name));
                                    return unique.length ? [...prev, ...unique] : prev;
                                  });
                                }
                                e.target.value = '';
                              }}
                              className="hidden" 
                              disabled={isLoading} 
                            />
                          </label>
                        </div>
                      </>
                    ) : (
                      <div className="flex-1">
                        <ResumeUploader onFilesChange={setResumeFiles} disabled={isLoading} />
                      </div>
                    )}
                  </div>
                  {resumeFiles.length > 0 && (
                    <div className="mt-3 flex justify-between items-center">
                      <span className="text-sm text-slate-600">
                        📁 {resumeFiles.length} resume{resumeFiles.length !== 1 ? 's' : ''} ready for analysis
                      </span>
                      <button 
                        onClick={() => setResumeFiles([])}
                        className="text-xs text-red-600 hover:underline"
                        disabled={isLoading}
                      >
                        Clear All
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex flex-col items-center">
                <button
                  onClick={handleAnalyze}
                  disabled={isAnalyzeDisabled}
                  className="w-full md:w-auto px-12 py-4 bg-indigo-600 text-white font-bold text-lg rounded-xl shadow-md hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-all duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  {isLoading ? 'Analyzing...' : 'Analyze & Shortlist'}
                </button>
                {error && <p className="text-red-500 mt-4 text-center">{error}</p>}
                {isLoading && typeof totalDuringAnalysis === 'number' && (
                  <div className="mt-4 w-full md:w-96">
                    <div className="bg-slate-200 rounded-full h-2 overflow-hidden">
                      <div className="bg-indigo-600 h-2 rounded-full animate-pulse" style={{ width: '25%' }} />
                    </div>
                    <p className="text-sm text-slate-600 mt-2">
                      Analyzing {totalDuringAnalysis} resume{totalDuringAnalysis !== 1 ? 's' : ''}… Parsed 0/{totalDuringAnalysis}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {isLoading && <Loader />}

          {!isLoading && analysis && (
            <div className="mt-12">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold text-slate-800">Shortlisting Summary</h2>
                <button
                  onClick={() => {
                    setAnalysis(null);
                    setExpandedResumeId(null);
                  }}
                  className="px-4 py-2 bg-slate-600 text-white rounded hover:bg-slate-700 text-sm font-medium"
                >
                  🔄 Re-analyze
                </button>
              </div>
              
              {/* Group Filter Controls */}
              <div className="mb-4 p-4 bg-slate-50 rounded-lg border">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm font-medium text-slate-700">Show Groups:</span>
                  {[
                    { key: 'strongly_consider', label: 'Strongly Consider', color: 'bg-green-100 text-green-700' },
                    { key: 'potential_fit', label: 'Potential Fit', color: 'bg-yellow-100 text-yellow-800' },
                    { key: 'rejected', label: 'Rejected', color: 'bg-red-100 text-red-700' }
                  ].map(({ key, label, color }) => (
                    <button
                      key={key}
                      onClick={() => {
                        const newVisible = new Set(visibleGroups);
                        if (newVisible.has(key)) {
                          newVisible.delete(key);
                        } else {
                          newVisible.add(key);
                        }
                        setVisibleGroups(newVisible);
                      }}
                      className={`px-3 py-1 rounded text-sm font-medium transition-all ${
                        visibleGroups.has(key) 
                          ? `${color} border border-current` 
                          : 'bg-white text-slate-500 border border-slate-300 hover:bg-slate-100'
                      }`}
                    >
                      {label} ({groupCounts[key] || 0})
                    </button>
                  ))}
                  <span className="text-xs text-slate-500 ml-2">
                    Showing: {filteredResults.length} of {(() => {
                      if (!analysis) return 0;
                      const seen = new Set<string>();
                      for (const r of analysis.results) seen.add(r.resume_id);
                      return seen.size;
                    })()} resumes
                  </span>
                  <button
                    onClick={handleDownloadCSV}
                    disabled={filteredResults.length === 0}
                    className="ml-4 px-3 py-1 bg-indigo-600 text-white text-sm font-medium rounded hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
                  >
                    📊 Download CSV
                  </button>
                </div>
              </div>

              <div className="mb-3 text-sm text-slate-600">
                {(() => {
                  const seen = new Set<string>();
                  for (const r of analysis.results) seen.add(r.resume_id);
                  const uniqueCount = seen.size;
                  const totalCount = typeof totalDuringAnalysis === 'number' ? totalDuringAnalysis : uniqueCount;
                  return `Parsed ${uniqueCount}/${totalCount} resume${uniqueCount !== 1 ? 's' : ''}.`;
                })()}
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full border border-slate-200 text-sm">
                  <thead className="bg-slate-100">
                    <tr>
                      <th className="p-2 text-left">Resume</th>
                      <th className="p-2 text-left">Group</th>
                      <th className="p-2 text-left">GitHub</th>
                      <th className="p-2 text-left">LinkedIn</th>
                      <th className="p-2 text-left">Criteria Met</th>
                      <th className="p-2 text-left">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredResults.map((r) => {
                      const total = r.yes_count + r.no_count;
                      const pct = total > 0 ? Math.round((r.yes_count / total) * 100) : 0;
                      const groupLabel = r.group === 'strongly_consider' ? 'Strongly Consider' : r.group === 'potential_fit' ? 'Potential Fit' : 'Rejected';
                      const isExpanded = expandedResumeId === r.resume_id;
                      
                      return (
                        <React.Fragment key={r.resume_id}>
                          <tr className="border-t">
                            <td className="p-2 font-mono text-slate-700">{r.resume_id}</td>
                            <td className="p-2">
                              <span className={
                                r.group === 'strongly_consider' ? 'px-2 py-1 rounded bg-green-100 text-green-700' :
                                r.group === 'potential_fit' ? 'px-2 py-1 rounded bg-yellow-100 text-yellow-800' :
                                'px-2 py-1 rounded bg-red-100 text-red-700'
                              } title={r.group_reason}>{groupLabel}</span>
                            </td>
                            <td className="p-2">
                              {r.has_github ? (
                                <a className="text-indigo-600 hover:underline" href={r.github_url} target="_blank" rel="noreferrer">Yes</a>
                              ) : (
                                <span className="text-slate-500">No</span>
                              )}
                            </td>
                            <td className="p-2">
                              {r.has_github && r.has_linkedin ? (
                                <a className="text-blue-600 hover:underline" href={r.linkedin_url} target="_blank" rel="noreferrer">Yes</a>
                              ) : (
                                <span className="text-slate-500">No</span>
                              )}
                            </td>
                            <td className="p-2">
                              <div className="w-48 bg-slate-200 h-3 rounded">
                                <div className="bg-indigo-600 h-3 rounded" style={{ width: `${pct}%` }}></div>
                              </div>
                              <div className="text-xs text-slate-600 mt-1">{r.yes_count} / {total} yes</div>
                            </td>
                            <td className="p-2">
                              <button className="text-indigo-700 hover:underline" onClick={() => setExpandedResumeId(isExpanded ? null : r.resume_id)}>
                                {isExpanded ? 'Hide' : 'View'}
                              </button>
                            </td>
                          </tr>
                          
                          {/* Inline Details Row */}
                          {isExpanded && (
                            <tr className="border-t bg-slate-50">
                              <td colSpan={6} className="p-0">
                                <div className="p-6 bg-white border-l-4 border-indigo-500 mx-2 my-2 rounded shadow-sm">
                                  <h4 className="text-lg font-bold text-slate-800 mb-2">{r.resume_id}</h4>
                                  <p className="text-slate-600 mb-4">{r.group_reason}</p>
                                  
                                  <div className="mt-4 flex gap-4">
                                    {r.has_github && (
                                      <div className="flex-1 p-3 bg-indigo-50 rounded-lg border border-indigo-200">
                                        <h5 className="font-semibold text-indigo-800 mb-2">GitHub Profile</h5>
                                        <div>
                                          <a className="text-indigo-600 hover:underline font-medium" href={r.github_url} target="_blank" rel="noreferrer">
                                            View Profile →
                                          </a>
                                        </div>
                                      </div>
                                    )}
                                    {r.has_github && r.has_linkedin && (
                                      <div className="flex-1 p-3 bg-blue-50 rounded-lg border border-blue-200">
                                        <h5 className="font-semibold text-blue-800 mb-2">LinkedIn Profile</h5>
                                        <div>
                                          <a className="text-blue-600 hover:underline font-medium" href={r.linkedin_url} target="_blank" rel="noreferrer">
                                            View Profile →
                                          </a>
                                        </div>
                                      </div>
                                    )}
                                  </div>

                                  {r.has_github && r.github_stats && (
                                    <div className="mt-4 p-4 bg-purple-50 rounded-lg border border-purple-200">
                                      <h5 className="font-semibold text-purple-800 mb-2">GitHub Statistics</h5>
                                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                                        <div>
                                          <div className="text-purple-600 font-medium">Public Repos</div>
                                          <div className="text-lg font-bold text-purple-800">{r.github_stats.public_repos || 0}</div>
                                        </div>
                                        <div>
                                          <div className="text-purple-600 font-medium">Stars Received</div>
                                          <div className="text-lg font-bold text-purple-800">{r.github_stats.total_stars || 0}</div>
                                        </div>
                                        <div>
                                          <div className="text-purple-600 font-medium">Followers</div>
                                          <div className="text-lg font-bold text-purple-800">{r.github_stats.followers || 0}</div>
                                        </div>
                                        <div>
                                          <div className="text-purple-600 font-medium">Recent Activity</div>
                                          <div className="text-lg font-bold text-purple-800">{r.github_stats.recent_activity || 0} repos</div>
                                        </div>
                                        <div>
                                          <div className="text-purple-600 font-medium">Total Forks</div>
                                          <div className="text-lg font-bold text-purple-800">{r.github_stats.total_forks || 0}</div>
                                        </div>
                                        {r.github_stats.company && (
                                          <div>
                                            <div className="text-purple-600 font-medium">Company</div>
                                            <div className="text-sm text-purple-800">{r.github_stats.company}</div>
                                          </div>
                                        )}
                                        {r.github_stats.location && (
                                          <div>
                                            <div className="text-purple-600 font-medium">Location</div>
                                            <div className="text-sm text-purple-800">{r.github_stats.location}</div>
                                          </div>
                                        )}
                                      </div>
                                      {r.github_stats.bio && (
                                        <div className="mt-3">
                                          <div className="text-purple-600 font-medium text-sm">Bio</div>
                                          <div className="text-sm text-purple-700 italic">{r.github_stats.bio}</div>
                                        </div>
                                      )}
                                    </div>
                                  )}
                                  
                                  <div className="mt-4">
                                    <h5 className="font-semibold text-slate-700 mb-2">Criteria breakdown</h5>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                      {r.answers.map((a) => (
                                        <div key={a.criterion_id} className={`p-3 rounded border ${String(a.answer).toLowerCase() === 'yes' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                                          <div className="flex items-center justify-between">
                                            <div className="font-medium text-slate-800 mr-2">{a.question}</div>
                                            <span className={`text-xs px-2 py-0.5 rounded ${String(a.answer).toLowerCase() === 'yes' ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}`}>{String(a.answer).toLowerCase() === 'yes' ? 'Yes' : 'No'}</span>
                                          </div>
                                          {a.reasons && a.reasons.length > 0 && (
                                            <ul className="list-disc ml-5 mt-1 text-sm text-slate-700">
                                              {a.reasons.map((reason, i) => (
                                                <li key={i}>{reason}</li>
                                              ))}
                                            </ul>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                    <div className="mt-4 text-sm text-slate-600">Yes: {r.yes_count} / {total} • No: {r.no_count}</div>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>

            </div>
          )}

        </div>
      </main>
      <footer className="text-center py-6 text-slate-500 text-sm">

      </footer>
    </div>
  );
}
