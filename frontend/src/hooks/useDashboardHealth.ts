// ─── useDashboardHealth Hook ──────────────────────────────────────
// Fetches all three dashboard endpoints in parallel.
// Returns combined health, import summary, and directive status data
// for the exec summary dock.

import { useState, useEffect, useCallback } from "react";
import { getProjectHealth, getImportSummary, getDirectiveStatus } from "@/api/dashboard";
import type {
  ProjectHealthResponse,
  ImportSummaryResponse,
  DirectiveStatusResponse,
} from "@/types/dashboard";

export interface DashboardHealthResult {
  health: ProjectHealthResponse | null;
  importSummary: ImportSummaryResponse | null;
  directiveStatus: DirectiveStatusResponse | null;
  loading: boolean;
  error: string | null;
  /** Force a re-fetch (e.g. after import or workflow action). */
  refresh: () => void;
}

export function useDashboardHealth(projectId?: string): DashboardHealthResult {
  const [health, setHealth] = useState<ProjectHealthResponse | null>(null);
  const [importSummary, setImportSummary] = useState<ImportSummaryResponse | null>(null);
  const [directiveStatus, setDirectiveStatus] = useState<DirectiveStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetchCount, setFetchCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const [healthData, importData, directiveData] = await Promise.all([
          getProjectHealth(projectId),
          getImportSummary(projectId),
          getDirectiveStatus(projectId),
        ]);

        if (!cancelled) {
          setHealth(healthData);
          setImportSummary(importData);
          setDirectiveStatus(directiveData);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load dashboard data",
          );
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [projectId, fetchCount]);

  const refresh = useCallback(() => {
    setFetchCount((c) => c + 1);
  }, []);

  return { health, importSummary, directiveStatus, loading, error, refresh };
}
