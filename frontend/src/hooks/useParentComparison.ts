// ─── useParentComparison Hook ─────────────────────────────────────
// Fetches bulk comparison data for all children of a parent item
// (project or milestone) using the comparison API's parent_item_id mode.
// Returns a Map<itemId, category> for quick lookup by list renderers.

import { useState, useEffect, useMemo, useContext } from "react";
import { postCompare, type ItemComparison, type ComparisonResponse } from "@/api/comparison";
import { TemporalCtx } from "@/context/ComparisonContext";

export interface ParentComparisonResult {
  /** Map from item ID to its comparison category. */
  categoryMap: Map<string, ItemComparison["category"]>;
  /** Full item comparison data keyed by item ID. */
  itemMap: Map<string, ItemComparison>;
  loading: boolean;
  error: string | null;
}

const EMPTY_CATEGORY_MAP = new Map<string, ItemComparison["category"]>();
const EMPTY_ITEM_MAP = new Map<string, ItemComparison>();

/**
 * Fetch comparison data for all children of a parent item.
 * Active only when comparison mode is engaged. Returns empty maps otherwise.
 */
export function useParentComparison(
  parentItemId: string | null,
): ParentComparisonResult {
  const ctx = useContext(TemporalCtx);
  const { isActive = false, fromContext = null, toContext = null, valueMode = "submitted" as const } = ctx?.state ?? {};

  const [response, setResponse] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isActive || !parentItemId || !fromContext || !toContext) {
      setResponse(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const data = await postCompare({
          parent_item_id: parentItemId,
          from_context_id: fromContext.id,
          to_context_id: toContext.id,
          mode: valueMode,
        });

        if (!cancelled) {
          setResponse(data);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Comparison failed");
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [parentItemId, isActive, fromContext?.id, toContext?.id, valueMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const categoryMap = useMemo(() => {
    if (!response) return EMPTY_CATEGORY_MAP;
    const map = new Map<string, ItemComparison["category"]>();
    for (const item of response.items) {
      map.set(item.item_id, item.category);
    }
    return map;
  }, [response]);

  const itemMap = useMemo(() => {
    if (!response) return EMPTY_ITEM_MAP;
    const map = new Map<string, ItemComparison>();
    for (const item of response.items) {
      map.set(item.item_id, item);
    }
    return map;
  }, [response]);

  return { categoryMap, itemMap, loading, error };
}
