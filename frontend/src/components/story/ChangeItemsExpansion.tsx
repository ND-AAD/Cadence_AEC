// ─── Change Items Expansion ───────────────────────────────────────
// Lazy-loaded expansion for property rows with workflow change items.
// Fetches change item(s) by ID on mount, renders old → new values
// with context labels. Each change item is navigable (page turn).
//
// This component is rendered inside a PropertyRow expansion when
// workflow.change_ids exist but comparison mode is not active.

import { useState, useEffect } from "react";
import { getItems } from "@/api/items";

interface ChangeItemsExpansionProps {
  /** Change item IDs to fetch and display. */
  changeIds: string[];
  /** Property name this expansion is for (to filter relevant changes). */
  propertyName: string;
  /** Navigation callback — click a change item to page-turn to Surface 2. */
  onNavigate: (itemId: string) => void;
}

interface ChangeDetail {
  id: string;
  oldValue: unknown;
  newValue: unknown;
  fromContext: string | null;
  toContext: string | null;
  source: string | null;
}

export function ChangeItemsExpansion({
  changeIds,
  propertyName,
  onNavigate,
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
          // The change item's "changes" dict maps property_name → { old, new }
          const changesDict = props.changes as Record<string, { old: unknown; new: unknown }> | undefined;

          if (changesDict && propertyName in changesDict) {
            // This change item has data for our specific property
            details.push({
              id: item.id,
              oldValue: changesDict[propertyName].old,
              newValue: changesDict[propertyName].new,
              fromContext: props.from_context_name as string | null ?? null,
              toContext: props.to_context_name as string | null ?? null,
              source: props.source_name as string | null ?? null,
            });
          } else if (changesDict) {
            // Change item exists but doesn't have this specific property —
            // show all changed properties from this item
            for (const [, vals] of Object.entries(changesDict)) {
              details.push({
                id: item.id,
                oldValue: vals.old,
                newValue: vals.new,
                fromContext: props.from_context_name as string | null ?? null,
                toContext: props.to_context_name as string | null ?? null,
                source: props.source_name as string | null ?? null,
              });
            }
          } else {
            // Fallback: use top-level previous_value / new_value
            details.push({
              id: item.id,
              oldValue: props.previous_value ?? null,
              newValue: props.new_value ?? null,
              fromContext: props.from_context_name as string | null ?? null,
              toContext: props.to_context_name as string | null ?? null,
              source: props.source_name as string | null ?? null,
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
              {formatVal(change.oldValue)}
            </span>
            <span className="text-trace text-xs">→</span>
            {/* New value */}
            <span className="font-mono text-pencil-ink">
              {formatVal(change.newValue)}
            </span>
            {/* Context labels if available */}
            {(change.fromContext || change.toContext) && (
              <span className="text-xs text-trace ml-1">
                {change.fromContext ?? "?"} → {change.toContext ?? "?"}
              </span>
            )}
          </div>
          {/* Navigate to change item (Surface 2) */}
          <button
            type="button"
            onClick={() => onNavigate(change.id)}
            className="text-xs text-pencil-ink hover:underline shrink-0"
          >
            View ›
          </button>
        </div>
      ))}
    </div>
  );
}

function formatVal(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return String(value);
}
