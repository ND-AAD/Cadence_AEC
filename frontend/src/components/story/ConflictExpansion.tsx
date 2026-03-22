// ─── Conflict Expansion (Surface 1) ──────────────────────────────
// Inline expansion for active conflict state.
// DS-2 §4.3 + §6.2: Quick triage — expand row, see both sources, resolve.
//
// Decision 11: Both sources rendered as peers. No privileged source.
//
// Layout:
//   CONFLICT · NEEDS REVIEW · CD
//   [Source A]  [value A]
//   [Source B]  [value B]
//   [affected item]  [identifier]           ›
//   ─────────────────────────────────
//   RESOLVE
//   ○ Source A   value A
//   ○ Source B   value B
//   ○ custom     [          ]
//   [Resolve]  [Hold]

import { useState } from "react";
import type { ResolutionMethod } from "@/api/actionItems";

/** A source's value in a conflict. */
export interface ConflictSource {
  /** Source item ID. */
  sourceId: string;
  /** Human-readable source name. */
  sourceName: string;
  /** The value this source asserts. */
  value: unknown;
}

interface ConflictExpansionProps {
  /** The property name. */
  propertyName: string;
  /** The two (or more) conflicting sources. */
  sources: ConflictSource[];
  /** The milestone/context label (e.g., "CD"). */
  contextLabel?: string;
  /** Current workflow status of the conflict. */
  status?: string;
  /** Conflict item ID (for API calls). */
  conflictItemId?: string;
  /** Called when user resolves the conflict. */
  onResolve?: (request: {
    chosen_value: string | null;
    chosen_source_id: string | null;
    method: ResolutionMethod;
  }) => void;
  /** Called when user puts the conflict on hold. */
  onHold?: () => void;
  /** Navigate to an item (source name click = Z-axis shift, affected item click). */
  onNavigate?: (itemId: string) => void;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

/** Map backend status to UX label. */
function statusLabel(status?: string): string {
  switch (status) {
    case "detected": return "Needs Review";
    case "in_review": return "In Review";
    case "hold": return "Hold";
    case "resolved": return "Accepted";
    default: return "Needs Review";
  }
}

export function ConflictExpansion({
  propertyName,
  sources,
  contextLabel,
  status,
  conflictItemId,
  onResolve,
  onHold,
  onNavigate,
}: ConflictExpansionProps) {
  // Resolution selection state.
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [customValue, setCustomValue] = useState("");
  const [useCustom, setUseCustom] = useState(false);

  const handleResolve = () => {
    if (!onResolve) return;
    if (useCustom) {
      onResolve({
        chosen_value: customValue,
        chosen_source_id: null,
        method: "manual_value",
      });
    } else if (selectedSourceId) {
      const source = sources.find((s) => s.sourceId === selectedSourceId);
      onResolve({
        chosen_value: source ? formatValue(source.value) : null,
        chosen_source_id: selectedSourceId,
        method: "chosen_source",
      });
    }
  };

  const canResolve = useCustom ? customValue.trim().length > 0 : !!selectedSourceId;

  return (
    <div className="space-y-3">
      {/* Status line */}
      <div className="flex items-center gap-2 text-xs">
        <span className="font-mono uppercase text-redline-ink">{propertyName}</span>
        <span className="text-trace">·</span>
        <span className="font-mono uppercase text-redline">{statusLabel(status)}</span>
        {contextLabel && (
          <>
            <span className="text-trace">·</span>
            <span className="text-graphite">{contextLabel}</span>
          </>
        )}
      </div>

      {/* Peer-sourced value display (Decision 11) */}
      <div className="space-y-1">
        {sources.map((source) => (
          <div
            key={source.sourceId}
            className="grid grid-cols-[100px_1fr] gap-x-3 items-baseline"
          >
            <button
              type="button"
              className="text-xs text-redline hover:text-redline-ink truncate text-left transition-colors duration-100"
              onClick={() => onNavigate?.(source.sourceId)}
              title={`Navigate to ${source.sourceName}`}
            >
              {source.sourceName}
            </button>
            <span className="text-sm text-redline-ink font-medium font-mono">
              {formatValue(source.value)}
            </span>
          </div>
        ))}
      </div>

      {/* Expansion rule */}
      <div
        className="h-px"
        style={{
          backgroundImage: "linear-gradient(var(--rule), var(--rule))",
          backgroundSize: "calc(100% - 48px - 16px) 1px",
          backgroundPosition: "48px 0",
          backgroundRepeat: "no-repeat",
        }}
      />

      {/* Resolution controls (Surface 1 — no rationale/decided-by) */}
      {(status === "detected" || status === "in_review") && onResolve && (
        <div className="space-y-2">
          <span className="text-xs font-mono uppercase text-graphite">Resolve</span>

          {/* Radio options for each source */}
          {sources.map((source) => (
            <label
              key={source.sourceId}
              className={`flex items-center gap-2 px-2 py-1 rounded text-sm cursor-pointer transition-colors duration-100 ${
                selectedSourceId === source.sourceId && !useCustom
                  ? "bg-stamp-wash"
                  : "hover:bg-board/20"
              }`}
            >
              <input
                type="radio"
                name={`resolve-${conflictItemId ?? propertyName}`}
                checked={selectedSourceId === source.sourceId && !useCustom}
                onChange={() => {
                  setSelectedSourceId(source.sourceId);
                  setUseCustom(false);
                }}
                className="accent-stamp"
              />
              <span className="text-xs text-graphite truncate w-24">{source.sourceName}</span>
              <span className="font-mono text-sm">{formatValue(source.value)}</span>
            </label>
          ))}

          {/* Custom value option */}
          <label
            className={`flex items-center gap-2 px-2 py-1 rounded text-sm cursor-pointer transition-colors duration-100 ${
              useCustom ? "bg-stamp-wash" : "hover:bg-board/20"
            }`}
          >
            <input
              type="radio"
              name={`resolve-${conflictItemId ?? propertyName}`}
              checked={useCustom}
              onChange={() => {
                setUseCustom(true);
                setSelectedSourceId(null);
              }}
              className="accent-stamp"
            />
            <span className="text-xs text-graphite w-24">custom</span>
            <input
              type="text"
              value={customValue}
              onChange={(e) => setCustomValue(e.target.value)}
              onFocus={() => {
                setUseCustom(true);
                setSelectedSourceId(null);
              }}
              className="flex-1 text-sm font-mono border border-rule rounded px-2 py-0.5 bg-transparent focus:outline-none focus:border-stamp"
              placeholder="Enter value…"
            />
          </label>

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleResolve();
              }}
              disabled={!canResolve}
              className="bg-stamp-wash text-stamp-ink border border-stamp rounded text-xs px-3 py-1 hover:bg-stamp/10 transition-colors duration-100 disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
            >
              Resolve
            </button>
            {onHold && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onHold();
                }}
                className="bg-transparent text-graphite border border-board rounded text-xs px-3 py-1 hover:text-ink hover:border-graphite transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
              >
                Hold
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
