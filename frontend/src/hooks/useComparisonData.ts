// ─── useComparisonData Hook ───────────────────────────────────────
// Fetches comparison data for a specific item across two contexts.
// Uses the ComparisonContext cache to avoid redundant API calls.

import { useState, useEffect, useCallback } from "react";
import { postCompare, type ItemComparison } from "@/api/comparison";
import { useComparisonContext } from "@/context/ComparisonContext";

export interface ComparisonDataResult {
  data: ItemComparison | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

/**
 * Fetch comparison data for a single item at the active comparison contexts.
 * Returns cached data if available; fetches from API otherwise.
 */
export function useComparisonData(
  itemId: string | null,
): ComparisonDataResult {
  const { state, getItemComparison, setItemData, setPending, setError } =
    useComparisonContext();
  const [loading, setLoading] = useState(false);
  const [error, setLocalError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const { isActive, fromContext, toContext } = state;

  useEffect(() => {
    // Don't fetch if comparison isn't active or IDs are missing.
    if (!isActive || !itemId || !fromContext || !toContext) {
      return;
    }

    // Check cache first.
    const cached = getItemComparison(itemId);
    if (cached) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setLocalError(null);
    setPending(true);

    (async () => {
      try {
        const response = await postCompare({
          item_ids: [itemId],
          from_context_id: fromContext.id,
          to_context_id: toContext.id,
        });

        if (cancelled) return;

        // Cache all returned items (usually just one).
        for (const item of response.items) {
          setItemData(item.item_id, item);
        }

        // If the item wasn't in the response, it's unchanged.
        if (!response.items.find((i) => i.item_id === itemId)) {
          setItemData(itemId, {
            item_id: itemId,
            identifier: null,
            item_type: "",
            category: "unchanged",
            changes: [],
          });
        }

        setPending(false);
        setLoading(false);
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Comparison failed";
          setLocalError(msg);
          setError(msg);
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [itemId, isActive, fromContext?.id, toContext?.id, retryCount]); // eslint-disable-line react-hooks/exhaustive-deps

  const retry = useCallback(() => setRetryCount((c) => c + 1), []);

  // Return cached data if available.
  const data = itemId ? getItemComparison(itemId) ?? null : null;

  return { data, loading, error, retry };
}
