// ─── Change Items Expansion ───────────────────────────────────────
// Lazy-loaded expansion for property rows with workflow change items.
// Fetches change item(s) by ID on mount, renders old → new values
// with context labels. Each change item is navigable (page turn).

import { useState, useEffect } from "react";
import { getItems } from "@/api/items";

interface ChangeItemsExpansionProps {
  /** Change item IDs to fetch and display. */
  changeIds: string[];
  /** Property name this expansion is for (to filter relevant changes). */
  propertyName: string;
  /** Display unit for value conversion (e.g., "in" for inches). */
  unit?: string | null;
  /** Navigation callback — click a change item to page-turn to Surface 2. */
  onNavigate: (itemId: string) => void;
  /** Acknowledge a change by its item ID and property name. */
  onAcknowledge?: (changeItemId: string, propertyName: string) => void;
}

interface ChangeDetail {
  id: string;
  oldValue: unknown;
  newValue: unknown;
  fromContext: string | null;
  toContext: string | null;
  source: string | null;
}

/** Conversion factors from canonical mm to display units. */
const MM_TO: Record<string, number> = { in: 25.4, ft: 304.8 };

function formatVal(value: unknown, unit?: string | null): string {
  if (value === null || value === undefined) return "—";

  // Try numeric conversion for dimension properties stored in mm
  if (unit && unit in MM_TO) {
    const num = Number(value);
    if (!isNaN(num) && num !== 0) {
      const converted = num / MM_TO[unit];
      const rounded = Math.round(converted * 100) / 100;
      return `${rounded} ${unit}`;
    }
  }

  return String(value);
}

export function ChangeItemsExpansion({
  changeIds,
  propertyName,
  unit,
  onNavigate,
  onAcknowledge,
}: ChangeItemsExpansionProps) {
  const [changes, setChanges] = useState<ChangeDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (changeIds.length === 0) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const items = await getItems(changeIds);
        if (cancelled) return;

        const details: ChangeDetail[] = [];
        for (const item of items) {
          const props = item.properties ?? {};
          const changesDict = props.changes as Record<string, { old: unknown; new: unknown }> | undefined;

          if (changesDict && propertyName in changesDict) {
            details.push({
              id: item.id,
              oldValue: changesDict[propertyName].old,
              newValue: changesDict[propertyName].new,
              fromContext: (props.from_context_name as string) ?? null,
              toContext: (props.to_context_name as string) ?? null,
              source: (props.source_name as string) ?? null,
            });
          } else if (changesDict) {
            for (const [, vals] of Object.entries(changesDict)) {
              details.push({
                id: item.id,
                oldValue: vals.old,
                newValue: vals.new,
                fromContext: (props.from_context_name as string) ?? null,
                toContext: (props.to_context_name as string) ?? null,
                source: (props.source_name as string) ?? null,
              });
            }
          } else {
            details.push({
              id: item.id,
              oldValue: props.previous_value ?? null,
              newValue: props.new_value ?? null,
              fromContext: (props.from_context_name as string) ?? null,
              toContext: (props.to_context_name as string) ?? null,
              source: (props.source_name as string) ?? null,
            });
          }
        }

        setChanges(details);
        setLoading(false);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load changes");
          setLoading(false);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [changeIds, propertyName]);

  if (loading) {
    return (
      <div className="px-4 py-3">
        <span className="text-xs text-trace animate-pulse">Loading changes…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-4 py-3">
        <span className="text-xs text-trace">Error: {error}</span>
      </div>
    );
  }

  if (changes.length === 0) {
    return (
      <div className="px-4 py-3">
        <span className="text-xs text-trace">No change details available.</span>
      </div>
    );
  }

  return (
    <div className="px-4 py-3 space-y-2">
      {changes.map((change, i) => (
        <div key={`${change.id}-${i}`} className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 text-sm">
            {/* Old value */}
            <span className="font-mono text-trace">
              {formatVal(change.oldValue, unit)}
            </span>
            <span className="text-trace text-xs">→</span>
            {/* New value */}
            <span className="font-mono text-pencil-ink">
              {formatVal(change.newValue, unit)}
            </span>
            {/* Context labels */}
            {(change.fromContext || change.toContext) && (
              <span className="text-xs text-trace ml-1">
                {change.fromContext ?? "?"} → {change.toContext ?? "?"}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {onAcknowledge && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onAcknowledge(change.id, propertyName); }}
                className="bg-pencil-wash text-pencil-ink border border-pencil rounded text-xs px-2 py-1 hover:bg-pencil/10 transition-colors duration-100"
              >
                Acknowledge
              </button>
            )}
            <button
              type="button"
              onClick={() => onNavigate(change.id)}
              className="text-xs text-pencil-ink hover:underline shrink-0"
            >
              View ›
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
