// ─── useTypeRegistry Hook ─────────────────────────────────────────
// Fetches and caches the type configuration registry.
// Called once on mount; type config is stable for the session.

import { useState, useEffect, useCallback } from "react";
import { getTypeRegistry } from "@/api/types";
import type { TypeRegistryResponse, TypeConfigEntry } from "@/types/navigation";

export interface TypeRegistryResult {
  /** The full type registry, or null if still loading. */
  registry: TypeRegistryResponse | null;
  /** Look up a single type config by name. */
  getType: (typeName: string) => TypeConfigEntry | undefined;
  loading: boolean;
  error: string | null;
  /** Force a re-fetch of the type registry (e.g. after creating a new type). */
  refresh: () => void;
}

export function useTypeRegistry(): TypeRegistryResult {
  const [registry, setRegistry] = useState<TypeRegistryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // StrictMode double-mounts: track with state, not ref, so the
  // second mount re-fetches after the first is cancelled.
  const [fetched, setFetched] = useState(false);

  useEffect(() => {
    if (fetched) return;

    let cancelled = false;
    (async () => {
      try {
        const data = await getTypeRegistry();
        if (!cancelled) {
          setRegistry(data);
          setLoading(false);
          setFetched(true);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load type registry");
          setLoading(false);
          setFetched(true);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [fetched]);

  const getType = useCallback(
    (typeName: string): TypeConfigEntry | undefined => {
      return registry?.[typeName];
    },
    [registry],
  );

  const refresh = useCallback(() => {
    setFetched(false);
    setLoading(true);
    setError(null);
  }, []);

  return { registry, getType, loading, error, refresh };
}
