// ─── useActionItems Hook ──────────────────────────────────────────
// Fetches action item rollup from the backend.
// Used by WorkflowTree, DashboardView, and ItemView for workflow
// item identification and pip navigation.
//
// Follows the useDashboardHealth pattern: useState + useEffect + cancellation.

import { useState, useEffect, useCallback } from "react";
import { getActionItems, type ActionItemRollup } from "@/api/actionItems";

export interface ActionItemsResult {
  rollup: ActionItemRollup | null;
  loading: boolean;
  error: string | null;
  /** Re-fetch after a status transition or resolution. */
  refresh: () => void;
}

export function useActionItems(projectId?: string): ActionItemsResult {
  const [rollup, setRollup] = useState<ActionItemRollup | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshCounter, setRefreshCounter] = useState(0);

  const refresh = useCallback(() => {
    setRefreshCounter((c) => c + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const data = await getActionItems(projectId);
        if (!cancelled) {
          setRollup(data);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load action items",
          );
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [projectId, refreshCounter]);

  return { rollup, loading, error, refresh };
}
