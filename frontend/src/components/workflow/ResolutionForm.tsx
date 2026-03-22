// ─── Resolution Form (Surface 2) ─────────────────────────────────
// Full resolution form for the workflow item view.
// DS-2 §6.3: Value selection, rationale, decided-by, note area.
//
// Surface 2 has all fields. Surface 1 (ConflictExpansion) only has
// value selection + Resolve/Hold buttons.
//
// Layout:
//   RESOLVE THIS CONFLICT
//   ○ Source A   value A
//   ○ Source B   value B
//   ○ custom     [          ]
//   rationale   [                    ]
//   decided by  [                    ]
//   NOTE (optional — creates a cairn)
//   [                                ]
//   [Start Review]  [Resolve]  [Hold]

import { useState, useCallback } from "react";
import type { ResolutionMethod } from "@/api/actionItems";

export interface ResolutionSource {
  sourceId: string;
  sourceName: string;
  value: string;
}

interface ResolutionFormProps {
  /** The conflicting sources and their values. */
  sources: ResolutionSource[];
  /** Current workflow status of the item. */
  status: string;
  /** Called when user starts review. */
  onStartReview?: () => void;
  /** Called when user resolves. */
  onResolve?: (request: {
    chosen_value: string | null;
    chosen_source_id: string | null;
    method: ResolutionMethod;
    rationale: string;
    decided_by: string;
    note?: string;
  }) => void;
  /** Called when user holds. */
  onHold?: () => void;
  /** Called when user resumes from hold. */
  onResume?: () => void;
}

export function ResolutionForm({
  sources,
  status,
  onStartReview,
  onResolve,
  onHold,
  onResume,
}: ResolutionFormProps) {
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [customValue, setCustomValue] = useState("");
  const [useCustom, setUseCustom] = useState(false);
  const [rationale, setRationale] = useState("");
  const [decidedBy, setDecidedBy] = useState("");
  const [note, setNote] = useState("");

  const handleResolve = useCallback(() => {
    if (!onResolve) return;
    if (useCustom) {
      onResolve({
        chosen_value: customValue,
        chosen_source_id: null,
        method: "manual_value",
        rationale,
        decided_by: decidedBy,
        note: note || undefined,
      });
    } else if (selectedSourceId) {
      const source = sources.find((s) => s.sourceId === selectedSourceId);
      onResolve({
        chosen_value: source?.value ?? null,
        chosen_source_id: selectedSourceId,
        method: "chosen_source",
        rationale,
        decided_by: decidedBy,
        note: note || undefined,
      });
    }
  }, [onResolve, useCustom, customValue, selectedSourceId, sources, rationale, decidedBy, note]);

  const canResolve = useCustom ? customValue.trim().length > 0 : !!selectedSourceId;
  const isHeld = status === "hold";
  const isActive = status === "detected" || status === "in_review";

  return (
    <div className="space-y-4">
      {/* Section header */}
      <h3 className="text-xs font-mono uppercase text-graphite tracking-wider">
        {isHeld ? "On Hold" : "Resolve This Conflict"}
      </h3>

      {/* Value selection (not shown when held) */}
      {isActive && (
        <div className="space-y-2">
          {sources.map((source) => (
            <label
              key={source.sourceId}
              className={`flex items-center gap-3 px-3 py-2 rounded cursor-pointer transition-colors duration-100 ${
                selectedSourceId === source.sourceId && !useCustom
                  ? "bg-stamp-wash"
                  : "hover:bg-board/20"
              }`}
            >
              <input
                type="radio"
                name="resolve-source"
                checked={selectedSourceId === source.sourceId && !useCustom}
                onChange={() => {
                  setSelectedSourceId(source.sourceId);
                  setUseCustom(false);
                }}
                className="accent-stamp"
              />
              <span className="text-xs text-graphite w-32 truncate">{source.sourceName}</span>
              <span className="font-mono text-sm text-ink">{source.value}</span>
            </label>
          ))}

          {/* Custom value */}
          <label
            className={`flex items-center gap-3 px-3 py-2 rounded cursor-pointer transition-colors duration-100 ${
              useCustom ? "bg-stamp-wash" : "hover:bg-board/20"
            }`}
          >
            <input
              type="radio"
              name="resolve-source"
              checked={useCustom}
              onChange={() => {
                setUseCustom(true);
                setSelectedSourceId(null);
              }}
              className="accent-stamp"
            />
            <span className="text-xs text-graphite w-32">custom value</span>
            <input
              type="text"
              value={customValue}
              onChange={(e) => setCustomValue(e.target.value)}
              onFocus={() => {
                setUseCustom(true);
                setSelectedSourceId(null);
              }}
              className="flex-1 text-sm font-mono border border-rule rounded px-2 py-1 bg-transparent focus:outline-none focus:border-stamp"
              placeholder="Enter value…"
            />
          </label>
        </div>
      )}

      {/* Full form fields (Surface 2 only) */}
      {isActive && (
        <div className="space-y-3">
          {/* Rationale */}
          <div className="space-y-1">
            <label className="text-xs text-graphite">rationale</label>
            <input
              type="text"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              className="w-full text-xs border border-rule rounded px-2 py-1.5 bg-transparent focus:outline-none focus:border-stamp"
              placeholder="Field measurement confirms value per code…"
            />
          </div>

          {/* Decided by */}
          <div className="space-y-1">
            <label className="text-xs text-graphite">decided by</label>
            <input
              type="text"
              value={decidedBy}
              onChange={(e) => setDecidedBy(e.target.value)}
              className="w-full text-xs font-mono border border-rule rounded px-2 py-1.5 bg-transparent focus:outline-none focus:border-stamp"
              placeholder="J. Martinez"
            />
          </div>
        </div>
      )}

      {/* Note area (available in all states) */}
      <div className="space-y-1">
        <label className="text-xs text-graphite">
          {isActive ? "Note (optional — creates a cairn)" : "Add a note"}
        </label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          className="w-full text-xs border border-rule rounded px-2 py-1.5 bg-transparent resize-y min-h-[48px] focus:outline-none focus:border-stamp"
          placeholder="Notes persist independently of resolution status."
        />
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-2 pt-1">
        {/* Start Review — visible only when detected */}
        {status === "detected" && onStartReview && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onStartReview();
            }}
            className="bg-transparent text-ink border border-rule-emphasis rounded text-xs px-3 py-1.5 hover:bg-board/20 hover:border-graphite transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
          >
            Start Review
          </button>
        )}

        {/* Resolve — visible when active (detected or in_review) */}
        {isActive && onResolve && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleResolve();
            }}
            disabled={!canResolve}
            className="bg-stamp-wash text-stamp-ink border border-stamp rounded text-xs px-3 py-1.5 hover:bg-stamp/10 transition-colors duration-100 disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
          >
            Resolve
          </button>
        )}

        {/* Hold — visible when active */}
        {isActive && onHold && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onHold();
            }}
            className="bg-transparent text-filed border border-rule-emphasis rounded text-xs px-3 py-1.5 hover:bg-filed-wash hover:border-filed transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
          >
            Hold
          </button>
        )}

        {/* Resume — visible only when held */}
        {isHeld && onResume && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onResume();
            }}
            className="bg-transparent text-ink border border-rule-emphasis rounded text-xs px-3 py-1.5 hover:bg-board/20 hover:border-graphite transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
          >
            Resume Review
          </button>
        )}
      </div>
    </div>
  );
}
