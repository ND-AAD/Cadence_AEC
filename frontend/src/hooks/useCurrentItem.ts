// ─── useCurrentItem Hook ──────────────────────────────────────────
// Fetches the full item data for a given item ID.
// Used for the story panel: shows properties, connections, etc.

import { useState, useEffect } from "react";
import { getItem } from "@/api/items";
import type { ItemResponse } from "@/types/navigation";

export interface CurrentItemResult {
  item: ItemResponse | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

export function useCurrentItem(itemId: string | null): CurrentItemResult {
  const [item, setItem] = useState<ItemResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (!itemId) {
      setItem(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const data = await getItem(itemId);
        if (!cancelled) {
          setItem(data);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load item");
          setLoading(false);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [itemId, retryCount]);

  const retry = () => setRetryCount((c) => c + 1);

  return { item, loading, error, retry };
}
