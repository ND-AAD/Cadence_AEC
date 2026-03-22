// ─── useResolvedProperties Hook ───────────────────────────────────
// Fetches resolved property data for a given item + context pair.
// Returns per-property status (agreed/single_source/conflicted/resolved)
// and effective values. Falls back gracefully if the endpoint is unavailable.

import { useState, useEffect } from "react";
import { getResolvedProperties, type ResolvedProperty } from "@/api/snapshots";

export interface ResolvedPropertiesResult {
  properties: ResolvedProperty[] | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

export function useResolvedProperties(
  itemId: string | null,
  contextId: string | null,
): ResolvedPropertiesResult {
  const [properties, setProperties] = useState<ResolvedProperty[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (!itemId || !contextId) {
      setProperties(null);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const data = await getResolvedProperties(itemId, contextId);
        if (!cancelled) {
          setProperties(data.properties);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          // Graceful fallback: if endpoint doesn't exist yet, just return null
          // so ItemView falls back to raw item.properties.
          setProperties(null);
          setError(err instanceof Error ? err.message : "Failed to load resolved properties");
          setLoading(false);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [itemId, contextId, retryCount]);

  const retry = () => setRetryCount((c) => c + 1);

  return { properties, loading, error, retry };
}
