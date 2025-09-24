import React, { useMemo } from 'react';
import type { QuestionsDoc } from '@/services/backendService';

export interface CriteriaBuilderState {
  selection: Record<string, boolean>;
  weights: Record<string, number>;
}

export default function CriteriaBuilder({
  criteriaDoc,
  state,
  onToggle,
  onWeight,
}: {
  criteriaDoc: QuestionsDoc;
  state: CriteriaBuilderState;
  onToggle: (id: string, val: boolean) => void;
  onWeight: (id: string, val: number) => void;
}) {
  const items = useMemo(() => criteriaDoc.criteria, [criteriaDoc]);

  return (
    <div className="space-y-3">
      {items.map((c) => (
        <div key={c.id} className="border rounded-lg p-4 bg-white">
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1">
              <h4 className="font-semibold text-slate-800">{c.name}</h4>
              <p className="text-slate-700">{c.question}</p>
              <p className="text-xs text-slate-500 mt-1">Rationale: {c.rationale}</p>
              <p className="text-xs text-slate-500">Expected evidence: {c.expected_evidence?.join(', ')}</p>
              <p className="text-xs text-slate-500">Leniency: {c.leniency_note}</p>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={!!state.selection[c.id]}
                  onChange={(e) => onToggle(c.id, e.target.checked)}
                />
                Include
              </label>
              <div className="flex flex-col items-end">
                <label className="text-xs text-slate-500">Weight: {state.weights[c.id]?.toFixed(2)}</label>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={state.weights[c.id] ?? 0}
                  onChange={(e) => onWeight(c.id, parseFloat(e.target.value))}
                />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
