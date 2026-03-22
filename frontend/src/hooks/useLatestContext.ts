// ─── useLatestContext Hook ────────────────────────────────────────
// Auto-derives the latest milestone context from the project's
// connected items. Looks for items of type "milestone" or "context"
// and picks the one with the highest ordinal value.
//
// Falls back to null if no milestones are found.

import { useState, useEffect } from "react";
import { getConnectedItems } from "@/api/connected";

export interface LatestContextResult {
  contextId: string | null;
  contextName: string | null;
  loading: boolean;
  error: string | null;
}

export function useLatestContext(projectId: string | null): LatestContextResult {
  const [contextId, setContextId] = useState<string | null>(null);
  const [contextName, setContextName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId || projectId === "root") {
      setContextId(null);
      setContextName(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        // Fetch connected items, looking for milestone/context types.
        const data = await getConnectedItems(projectId, {
          types: ["milestone", "context"],
        });

        if (cancelled) return;

        // Find the milestone group.
        const milestoneGroup =
          data.connected.find((g) => g.item_type === "milestone") ??
          data.connected.find((g) => g.item_type === "context");

        if (milestoneGroup && milestoneGroup.items.length > 0) {
          // Pick the last item (highest ordinal — items come sorted from backend).
          const latest = milestoneGroup.items[milestoneGroup.items.length - 1];
          setContextId(latest.id);
          setContextName(latest.identifier ?? latest.item_type);
        } else {
          setContextId(null);
          setContextName(null);
        }
        setLoading(false);
      } catch (err) {
        if (!cancelled) {
          setContextId(null);
          setContextName(null);
          setError(err instanceof Error ? err.message : "Failed to derive context");
          setLoading(false);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [projectId]);

  return { contextId, contextName, loading, error };
}
