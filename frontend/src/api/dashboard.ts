// ─── Dashboard API ────────────────────────────────────────────────
// Thin wrappers for WP-13a dashboard endpoints.
// Follows the same pattern as api/items.ts.

import { apiGet } from "./client";
import type {
  ProjectHealthResponse,
  ImportSummaryResponse,
  DirectiveStatusResponse,
  AffectedItemsResponse,
} from "@/types/dashboard";

/**
 * Fetch project-level health summary.
 * GET /api/v1/dashboard/health
 */
export function getProjectHealth(
  projectId?: string,
): Promise<ProjectHealthResponse> {
  const params = projectId ? `?project=${projectId}` : "";
  return apiGet<ProjectHealthResponse>(`/v1/dashboard/health${params}`);
}

/**
 * Fetch most recent import summary.
 * GET /api/v1/dashboard/import-summary
 */
export function getImportSummary(
  projectId?: string,
): Promise<ImportSummaryResponse> {
  const params = projectId ? `?project=${projectId}` : "";
  return apiGet<ImportSummaryResponse>(`/v1/dashboard/import-summary${params}`);
}

/**
 * Fetch directive status rollup grouped by target source.
 * GET /api/v1/dashboard/directive-status
 */
export function getDirectiveStatus(
  projectId?: string,
): Promise<DirectiveStatusResponse> {
  const params = projectId ? `?project=${projectId}` : "";
  return apiGet<DirectiveStatusResponse>(
    `/v1/dashboard/directive-status${params}`,
  );
}

/**
 * Fetch affected items for the workflow perspective.
 * GET /api/v1/dashboard/affected-items
 */
export function getAffectedItems(
  projectId?: string,
): Promise<AffectedItemsResponse> {
  const params = projectId ? `?project=${projectId}` : "";
  return apiGet<AffectedItemsResponse>(
    `/v1/dashboard/affected-items${params}`,
  );
}
