import React from 'react';
import SinglePage from './SinglePage';

export default function App() {
  return <SinglePage />;
}
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
            <ResumeUploader onFilesChange={setResumeFiles} disabled={isLoading} />
          </div>
                  </div>
                  <div>
                    <label className="block text-sm text-slate-600 mb-1">How many criteria?</label>
                    <input type="range" min={5} max={10} step={1} value={nCriteria} onChange={e=>setNCriteria(parseInt(e.target.value))} className="w-full" />
                    <div className="text-sm text-slate-500">{nCriteria}</div>
                  </div>
                </div>
                <div className="mt-4">
                  <label className="block text-sm text-slate-600 mb-1">Job Description (required)</label>
                  <textarea className="w-full h-40 border rounded px-3 py-2" value={jobDescription} onChange={e=>setJobDescription(e.target.value)} placeholder="Paste the full JD…" />
                </div>
                <div className="mt-4">
                  <label className="block text-sm text-slate-600 mb-1">HR Notes (optional)</label>
                  <textarea className="w-full h-28 border rounded px-3 py-2" value={hrNotes} onChange={e=>setHrNotes(e.target.value)} placeholder="What should be emphasized…" />
                </div>
                <div className="mt-4 flex flex-col items-start gap-3">
                  <button onClick={onGenerateCriteria} disabled={criteriaLoading || !jobDescription.trim()} className="px-6 py-3 bg-indigo-600 text-white rounded-lg disabled:bg-slate-300">{criteriaLoading ? 'Generating…' : 'Generate criteria'}</button>
                  {criteriaLoading && (
                    <div className="w-full md:w-96">
                      <div className="bg-slate-200 rounded-full h-2 overflow-hidden">
                        <div className="bg-indigo-600 h-2 rounded-full animate-pulse" style={{ width: '50%' }} />
                      </div>
                      <p className="text-sm text-slate-600 mt-2">Generating criteria…</p>
                    </div>
                  )}
                </div>
              </div>

              {criteriaDoc && (
                <div className="p-8 bg-white rounded-2xl shadow-lg border border-slate-200">
                  <h3 className="text-xl font-semibold text-slate-800 mb-2">Criteria (questions) to be used</h3>
                  <ol className="list-decimal ml-6 text-slate-700 mb-4">
                    {criteriaDoc.criteria.map((c, i) => (
                      <li key={c.id} className="mb-1">{c.question}</li>
                    ))}
                  </ol>

                  <div className="my-4 h-px bg-slate-200" />
                  <h3 className="text-lg font-semibold mb-2">Step 1A — Select and customize criteria (optional)</h3>
                  <p className="text-sm text-slate-600 mb-4">Choose which criteria to keep, adjust weights, or add custom criteria. Then click 'Finalize criteria'.</p>

                  <CriteriaBuilder
                    criteriaDoc={criteriaDoc}
                    state={criteriaState}
                    onToggle={onToggleCriterion}
                    onWeight={onWeightCriterion}
                  />

                  <div className="my-6 h-px bg-slate-200" />
                  <h4 className="font-semibold mb-2">Add a custom criterion</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-slate-600 mb-1">Name</label>
                      <input className="w-full border rounded px-3 py-2" value={customName} onChange={e=>setCustomName(e.target.value)} />
                    </div>
                    <div>
                      <label className="block text-sm text-slate-600 mb-1">Weight</label>
                      <input type="number" step={0.01} min={0} max={1} className="w-full border rounded px-3 py-2" value={customWeight} onChange={e=>setCustomWeight(parseFloat(e.target.value)||0)} />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm text-slate-600 mb-1">Yes/No question</label>
                      <textarea className="w-full border rounded px-3 py-2 h-20" value={customQuestion} onChange={e=>setCustomQuestion(e.target.value)} />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm text-slate-600 mb-1">Tags (comma-separated)</label>
                      <input className="w-full border rounded px-3 py-2" value={customTags} onChange={e=>setCustomTags(e.target.value)} />
                    </div>
                    <div className="md:col-span-2">
                      <button onClick={onAddCustomCriterion} className="px-4 py-2 bg-slate-800 text-white rounded">Add criterion</button>
                    </div>
                  </div>

                  <div className="mt-6">
                    <button onClick={onFinalizeCriteria} className="px-6 py-3 bg-green-600 text-white rounded-lg">Finalize criteria</button>
                  </div>
                </div>
              )}

              <div className="p-8 bg-white rounded-2xl shadow-lg border border-slate-200">
                <h2 className="text-2xl font-bold text-slate-700 mb-1">Step 2 — Upload resumes and run analysis</h2>
                <p className="text-slate-500 mb-6">Upload multiple resumes in PDF, DOCX, or TXT.</p>
                <MultiResumeUploader onFilesChange={setCriteriaFiles} disabled={isLoading} />
                <div className="mt-4 flex items-center gap-3">
                  <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" checked={strictMode} onChange={e=>setStrictMode(e.target.checked)} />
                    Strict mode (higher bar for "Strongly Consider")
                  </label>
                  <span className="text-xs text-slate-500">Current thresholds — Strongly Consider ≥ {thresholds.strong}, Potential Fit ≥ {thresholds.potential}</span>
                </div>
                <div className="mt-4 flex flex-col items-start gap-3">
                  <button onClick={onAnalyzeWithCriteria} disabled={analyzeLoading || !((finalCriteriaDoc||criteriaDoc) && criteriaFiles.length>0)} className="px-6 py-3 bg-indigo-600 text-white rounded-lg disabled:bg-slate-300">{analyzeLoading ? 'Running…' : 'Run analysis'}</button>
                  {analyzeLoading && (
                    <div className="w-full md:w-96">
                      <div className="bg-slate-200 rounded-full h-2 overflow-hidden">
                        <div className="bg-indigo-600 h-2 rounded-full animate-pulse" style={{ width: '60%' }} />
                      </div>
                      <p className="text-sm text-slate-600 mt-2">
                        Analyzing {criteriaFiles.length} resume{criteriaFiles.length!==1 ? 's' : ''}… This may take a minute depending on file size.
                      </p>
                    </div>
                  )}
                </div>

                {/* Render latest results from window stash if present */}
                {typeof window !== 'undefined' && (window as any).__lastAnalyzeResult && (()=>{
                  const { resp, weightById, totalWeight, critDoc } = (window as any).__lastAnalyzeResult as { resp: any, weightById: Record<string,number>, totalWeight: number, critDoc: QuestionsDoc };
                  const rows = (resp.results||[]).map((r: any) => {
                    let wYes = 0;
                    (r.answers||[]).forEach((a: any) => { if (a.answer === 'yes' && weightById[a.criterion_id]) wYes += weightById[a.criterion_id]; });
                    const weighted = Math.round((wYes / totalWeight) * 10000) / 10000;
                    const group = weighted >= thresholds.strong ? 'Strongly Consider' : weighted >= thresholds.potential ? 'Potential Fit' : 'Rejected';
                    return { Resume: r.resume_id, Yes: r.yes_count||0, No: r.no_count||0, WeightedScore: weighted, Group: group, Relevance: r.majority_pass ? 'Relevant' : 'Not Relevant', answers: r.answers };
                  });
                  return (
                    rows.length > 0 ? (
                      <div className="mt-6">
                        <h3 className="text-xl font-semibold">Results</h3>
                        <div className="overflow-auto mt-2">
                          <table className="min-w-full text-sm">
                            <thead>
                              <tr className="text-left text-slate-600">
                                {['Resume','Yes','No','WeightedScore','Group','Relevance'].map(h=> <th key={h} className="px-3 py-2 border-b">{h}</th>)}
                              </tr>
                            </thead>
                            <tbody>
                              {rows.map((row: any)=> (
                                <tr key={row.Resume} className="hover:bg-slate-50">
                                  <td className="px-3 py-2 border-b align-top">{row.Resume}</td>
                                  <td className="px-3 py-2 border-b align-top">{row.Yes}</td>
                                  <td className="px-3 py-2 border-b align-top">{row.No}</td>
                                  <td className="px-3 py-2 border-b align-top">{row.WeightedScore}</td>
                                  <td className="px-3 py-2 border-b align-top">{row.Group}</td>
                                  <td className="px-3 py-2 border-b align-top">{row.Relevance}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>

                        {/* Per-resume details */}
                        <div className="mt-6 space-y-3">
                          {rows.map((row: any) => (
                            <details key={`det-${row.Resume}`} className="bg-slate-50 rounded border p-3">
                              <summary className="cursor-pointer font-semibold">{row.Resume} — details</summary>
                              <div className="mt-2">
                                {/* Capability charts */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                                  <div>
                                    <div className="text-sm text-slate-700 mb-1">Weighted capability score</div>
                                    <div className="bg-slate-200 rounded-full h-3 overflow-hidden">
                                      <div className="bg-emerald-600 h-3 rounded-full" style={{ width: `${Math.min(100, Math.max(0, row.WeightedScore*100))}%` }} />
                                    </div>
                                    <div className="text-xs text-slate-500 mt-1">{(row.WeightedScore*100).toFixed(1)}%</div>
                                  </div>
                                  <div>
                                    <div className="text-sm text-slate-700 mb-1">Yes / No answers</div>
                                    <div className="flex h-3 rounded-full overflow-hidden bg-slate-200">
                                      {(() => {
                                        const total = (row.Yes||0) + (row.No||0);
                                        const yesPct = total ? (row.Yes/total)*100 : 0;
                                        const noPct = total ? (row.No/total)*100 : 0;
                                        return (
                                          <>
                                            <div className="bg-indigo-600" style={{ width: `${yesPct}%` }} />
                                            <div className="bg-rose-500" style={{ width: `${noPct}%` }} />
                                          </>
                                        );
                                      })()}
                                    </div>
                                    <div className="text-xs text-slate-500 mt-1">Yes: {row.Yes} • No: {row.No}</div>
                                  </div>
                                </div>
                                {/* Brief grouping explanation */}
                                <p className="text-sm text-slate-700 mb-3">
                                  Grouped as <strong>{row.Group}</strong> because weighted score {row.WeightedScore.toFixed(2)} {row.WeightedScore >= thresholds.strong ? `≥ Strongly Consider threshold ${thresholds.strong}` : row.WeightedScore >= thresholds.potential ? `≥ Potential Fit threshold ${thresholds.potential}` : `< ${thresholds.potential}`}, with Yes={row.Yes} and No={row.No}.
                                </p>
                                <h4 className="font-semibold">Top strengths (criteria matched)</h4>
                                <div className="overflow-auto">
                                  <table className="min-w-full text-sm mt-1">
                                    <thead><tr className="text-left text-slate-600"><th className="px-2 py-1">Criterion</th><th className="px-2 py-1">Question</th><th className="px-2 py-1">Answer</th><th className="px-2 py-1">Weight</th><th className="px-2 py-1">Reasons</th></tr></thead>
                                    <tbody>
                                      {row.answers.filter((a: any)=>a.answer==='yes').map((a: any)=> (
                                        <tr key={`${row.Resume}-${a.criterion_id}-y`}>
                                          <td className="px-2 py-1 border-t">{a.criterion_id}</td>
                                          <td className="px-2 py-1 border-t">{a.question}</td>
                                          <td className="px-2 py-1 border-t">{a.answer}</td>
                                          <td className="px-2 py-1 border-t">{weightById[a.criterion_id] || 0}</td>
                                          <td className="px-2 py-1 border-t">{(a.reasons||[]).slice(0,3).join('; ')}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                                <h4 className="font-semibold mt-4">Gaps (criteria not matched)</h4>
                                <div className="overflow-auto">
                                  <table className="min-w-full text-sm mt-1">
                                    <thead><tr className="text-left text-slate-600"><th className="px-2 py-1">Criterion</th><th className="px-2 py-1">Question</th><th className="px-2 py-1">Answer</th><th className="px-2 py-1">Weight</th><th className="px-2 py-1">Reasons</th></tr></thead>
                                    <tbody>
                                      {row.answers.filter((a: any)=>a.answer!=='yes').map((a: any)=> (
                                        <tr key={`${row.Resume}-${a.criterion_id}-n`}>
                                          <td className="px-2 py-1 border-t">{a.criterion_id}</td>
                                          <td className="px-2 py-1 border-t">{a.question}</td>
                                          <td className="px-2 py-1 border-t">{a.answer}</td>
                                          <td className="px-2 py-1 border-t">{weightById[a.criterion_id] || 0}</td>
                                          <td className="px-2 py-1 border-t">{(a.reasons||[]).slice(0,3).join('; ')}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            </details>
                          ))}
                        </div>
                      </div>
                    ) : null
                  );
                })()}
              </div>
            </>
          )}

        </div>

        {isLoading && <Loader />}

<<<<<<< HEAD
        {!isLoading && activeTab==='gemini' && hasResults && (
          <div className="mt-12">
            <ResultsDisplay rankedCandidates={rankedCandidates} rejectedCandidates={rejectedCandidates} />
          </div>
        )}
      </main>
      {/* 
      <footer className="text-center py-6 text-slate-500 text-sm">
        <p>Powered by Gemini API and FastAPI + OpenAI</p>
=======
      </main>
      {/* 
      <footer className="text-center py-6 text-slate-500 text-sm">
        <p>Powered by FastAPI + OpenAI</p>
>>>>>>> feature/apoorva-initial-upload
      </footer>
    </div>
  );
}
*/}