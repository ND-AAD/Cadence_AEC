// ─── Hold Expansion ──────────────────────────────────────────────
// Expansion content for a held workflow item.
// DS-2 §6.5: All information preserved, urgency removed.
//
// Layout:
//   CONFLICT · HOLD · CD
//   [Source A]  [value]    (dimmed, filed color)
//   [Resume Review]

import type { ConflictSource } from "./ConflictExpansion";

interface HoldExpansionProps {
  /** The property name. */
  propertyName: string;
  /** The type of held item: "conflict", "change", or "directive". */
  itemType: "conflict" | "change" | "directive";
  /** The conflicting sources (for conflicts) or change values. */
  sources?: ConflictSource[];
  /** Context label (e.g., "CD"). */
  contextLabel?: string;
  /** From/to context labels for changes. */
  fromContextName?: string;
  toContextName?: string;
  /** Old/new values for changes. */
  oldValue?: unknown;
  newValue?: unknown;
  /** Called when user resumes review. */
  onResume?: () => void;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function typeLabel(itemType: string): string {
  switch (itemType) {
    case "conflict": return "CONFLICT";
    case "change": return "CHANGE";
    case "directive": return "DIRECTIVE";
    default: return itemType.toUpperCase();
  }
}

export function HoldExpansion({
  propertyName,
  itemType,
  sources,
  contextLabel,
  fromContextName,
  toContextName,
  oldValue,
  newValue,
  onResume,
}: HoldExpansionProps) {
  return (
    <div className="space-y-3">
      {/* Status line */}
      <div className="flex items-center gap-2 text-xs">
        <span className="font-mono uppercase text-filed">{propertyName}</span>
        <span className="text-trace">·</span>
        <span className="font-mono uppercase text-filed">
          {typeLabel(itemType)} · Hold
        </span>
        {contextLabel && (
          <>
            <span className="text-trace">·</span>
            <span className="text-filed">{contextLabel}</span>
          </>
        )}
        {fromContextName && toContextName && (
          <>
            <span className="text-trace">·</span>
            <span className="text-filed">
              {fromContextName}
              <span className="mx-1.5 text-trace">→</span>
              {toContextName}
            </span>
          </>
        )}
      </div>

      {/* Dimmed source values (conflict) */}
      {sources && sources.length > 0 && (
        <div className="space-y-1">
          {sources.map((source) => (
            <div
              key={source.sourceId}
              className="grid grid-cols-[100px_1fr] gap-x-3 items-baseline"
            >
              <span className="text-xs text-filed truncate">
                {source.sourceName}
              </span>
              <span className="text-sm text-filed font-mono">
                {formatValue(source.value)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Dimmed change values */}
      {itemType === "change" && oldValue !== undefined && newValue !== undefined && (
        <div className="space-y-1">
          {fromContextName && (
            <div className="grid grid-cols-[100px_1fr] gap-x-3 items-baseline">
              <span className="text-xs text-filed truncate">{fromContextName}</span>
              <span className="text-sm text-filed font-mono">
                {formatValue(oldValue)}
              </span>
            </div>
          )}
          {toContextName && (
            <div className="grid grid-cols-[100px_1fr] gap-x-3 items-baseline">
              <span className="text-xs text-filed truncate">{toContextName}</span>
              <span className="text-sm text-filed font-mono">
                {formatValue(newValue)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Resume button */}
      {onResume && (
        <div className="flex items-center pt-1">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onResume();
            }}
            className="bg-transparent text-ink border border-rule-emphasis rounded text-xs px-3 py-1 hover:bg-board/20 hover:border-graphite transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
          >
            Resume Review
          </button>
        </div>
      )}
    </div>
  );
}
