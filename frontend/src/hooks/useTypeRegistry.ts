// ─── useTypeRegistry Hook ─────────────────────────────────────────
// Fetches and caches the type configuration registry.
// Uses a module-level cache so all component instances share the same data.

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

// ── Module-level shared cache ──
let cachedRegistry: TypeRegistryResponse | null = null;
let fetchPromise: Promise<TypeRegistryResponse> | null = null;
let cacheVersion = 0;

function fetchShared(): Promise<TypeRegistryResponse> {
  if (!fetchPromise) {
    fetchPromise = getTypeRegistry()
      .then((data) => {
        cachedRegistry = data;
        fetchPromise = null;
        return data;
      })
      .catch((err) => {
        fetchPromise = null;
        throw err;
      });
  }
  return fetchPromise;
}

export function useTypeRegistry(): TypeRegistryResult {
  const [registry, setRegistry] = useState<TypeRegistryResponse | null>(cachedRegistry);
  const [loading, setLoading] = useState(!cachedRegistry);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(cacheVersion);

  useEffect(() => {
    // If cache is already populated and version matches, skip fetch.
    if (cachedRegistry && version === cacheVersion) {
      setRegistry(cachedRegistry);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    fetchShared()
      .then((data) => {
        if (!cancelled) {
          setRegistry(data);
          setLoading(false);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load type registry");
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [version]);

  const getType = useCallback(
    (typeName: string): TypeConfigEntry | undefined => {
      return registry?.[typeName];
    },
    [registry],
  );

  const refresh = useCallback(() => {
    cachedRegistry = null;
    fetchPromise = null;
    cacheVersion++;
    setVersion(cacheVersion);
  }, []);

  return { registry, getType, loading, error, refresh };
}
