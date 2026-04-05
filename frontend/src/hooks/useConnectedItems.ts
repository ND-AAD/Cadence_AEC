// ─── useConnectedItems Hook ───────────────────────────────────────
// Fetches connected items for a given item ID.
// Re-fetches when the itemId changes (i.e., on navigation).

import { useState, useEffect } from "react";
import { getConnectedItems, type ConnectedItemsOptions } from "@/api/connected";
import type { ConnectedItemsResponse } from "@/types/navigation";

export interface ConnectedItemsResult {
  data: ConnectedItemsResponse | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

export function useConnectedItems(
  itemId: string | null,
  excludeIdsOrOptions?: string[] | ConnectedItemsOptions,
): ConnectedItemsResult {
  const [data, setData] = useState<ConnectedItemsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  // Normalize options.
  const options: ConnectedItemsOptions | undefined = Array.isArray(excludeIdsOrOptions)
    ? { exclude: excludeIdsOrOptions }
    : excludeIdsOrOptions;

  useEffect(() => {
    if (!itemId) {
      setData(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const result = await getConnectedItems(itemId, options);
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load connected items");
          setLoading(false);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [itemId, options?.context, retryCount]); // eslint-disable-line react-hooks/exhaustive-deps

  const retry = () => setRetryCount((c) => c + 1);

  return { data, loading, error, retry };
}
