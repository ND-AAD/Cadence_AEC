// ─── Property Expansion ───────────────────────────────────────────
// Expandable detail panel for a property change (cairn gesture).
// DS-2 §4: Row body click expands in-place to show change detail.

import type { PropertyChange } from "@/api/comparison";

/** Conversion factors from canonical mm to display units. */
const MM_TO: Record<string, number> = { in: 25.4, ft: 304.8 };

interface PropertyExpansionProps {
  /** The property key/name. */
  propertyName: string;
  /** The change data from the comparison API. */
  change: PropertyChange;
  /** Display name for the "from" context. */
  fromContextName: string;
  /** Display name for the "to" context. */
  toContextName: string;
  /** Display unit for value conversion (e.g., "in" for inches). */
  unit?: string | null;
  /** Called when user acknowledges the change. */
  onAcknowledge?: () => void;
  /** Called when user wants to hold/defer the change. */
  onHold?: () => void;
  /** Navigate to the affected item (if applicable). */
  onNavigateToItem?: (itemId: string) => void;
}

function formatValue(value: unknown, unit?: string | null): string {
  if (value === null || value === undefined) return "—";

  if (unit && unit in MM_TO) {
    const num = Number(value);
    if (!isNaN(num) && num !== 0) {
      const converted = num / MM_TO[unit];
      const rounded = Math.round(converted * 100) / 100;
      return `${rounded} ${unit}`;
    }
  }

  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

export function PropertyExpansion({
  propertyName,
  change,
  fromContextName,
  toContextName,
  unit,
  onAcknowledge,
  onHold,
}: PropertyExpansionProps) {
  return (
    <div className="space-y-3">
      {/* Status line */}
      <div className="flex items-center gap-2 text-xs">
        <span className="font-mono uppercase text-pencil-ink">{propertyName}</span>
        <span className="text-trace">·</span>
        <span className={`font-mono uppercase ${onAcknowledge ? "text-pencil" : "text-stamp"}`}>
          {onAcknowledge ? "Needs Review" : "Accepted"}
        </span>
        <span className="text-trace">·</span>
        <span className="text-graphite">
          {fromContextName}
          <span className="mx-1.5 text-trace">→</span>
          {toContextName}
        </span>
      </div>

      {/* Value comparison */}
      <div className="space-y-1">
        <div className="grid grid-cols-[100px_1fr] gap-x-3 items-baseline">
          <span className="text-xs text-trace truncate">{fromContextName}</span>
          <span className="text-sm text-trace font-mono">
            {formatValue(change.old_value, unit)}
          </span>
        </div>
        <div className="grid grid-cols-[100px_1fr] gap-x-3 items-baseline">
          <span className="text-xs text-pencil-ink truncate">{toContextName}</span>
          <span className="text-sm text-pencil-ink font-medium font-mono">
            {formatValue(change.new_value, unit)}
          </span>
        </div>
      </div>

      {/* Source attribution (if available) */}
      {change.source && (
        <div className="text-xs text-graphite">
          Source: <span className="font-mono">{change.source}</span>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        {onAcknowledge && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onAcknowledge();
            }}
            className="bg-pencil-wash text-pencil-ink border border-pencil rounded text-xs px-2 py-1 hover:bg-pencil/10 transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
          >
            Acknowledge
          </button>
        )}
        {onHold && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onHold();
            }}
            className="bg-transparent text-graphite border border-board rounded text-xs px-2 py-1 hover:text-ink hover:border-graphite transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
          >
            Hold
          </button>
        )}
      </div>
    </div>
  );
}
