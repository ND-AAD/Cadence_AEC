// ─── Action Items + Resolution API ───────────────────────────────
// Endpoints for conflict resolution, directives, and action item rollups.
// WP-12a backend: resolve, fulfill, bulk-resolve, action-items, directives.
// Separated from workflow.ts (status transitions) per FE-3/4 plan.

import { apiGet, apiPost } from "./client";

// ─── Enums ──────────────────────────────────────────────────────

export type ResolutionMethod = "chosen_source" | "manual_value";

// ─── Request Types ──────────────────────────────────────────────

export interface ConflictResolveRequest {
  /** The value to use (required for manual_value). */
  chosen_value?: string | null;
  /** The source whose value was chosen (required for chosen_source). */
  chosen_source_id?: string | null;
  /** Resolution method. */
  method: ResolutionMethod;
  /** Free-text reasoning behind the decision. */
  rationale: string;
  /** Who made the decision. */
  decided_by: string;
}

export interface BulkResolveEntry {
  conflict_item_id: string;
  chosen_value?: string | null;
  chosen_source_id?: string | null;
  method: ResolutionMethod;
  rationale: string;
  decided_by: string;
}

export interface BulkResolveRequest {
  resolutions: BulkResolveEntry[];
}

// ─── Response Types ─────────────────────────────────────────────

export interface ConflictResolveResponse {
  /** The decision item created by the resolution. */
  decision_item: {
    id: string;
    item_type: string;
    identifier: string | null;
    properties: Record<string, unknown>;
  };
  conflict_item_id: string;
  conflict_updated: boolean;
  directives_created: number;
  directives_fulfilled: number;
}

export interface DirectiveFulfillResponse {
  directive_item_id: string;
  status: string;
}

export interface BulkResolveResult {
  conflict_item_id: string;
  success: boolean;
  error: string | null;
  decision_item_id: string | null;
  directives_created: number;
}

export interface BulkResolveResponse {
  total_attempted: number;
  total_succeeded: number;
  total_failed: number;
  results: BulkResolveResult[];
}

export interface ActionItemRollup {
  changes_pending: number;
  conflicts_pending: number;
  directives_pending: number;
  total_action_items: number;
  by_type: Record<string, number>;
  by_property: Record<string, Record<string, number>>;
}

export interface DirectiveDetail {
  id: string;
  identifier: string | null;
  property_name: string;
  target_value: string | null;
  target_source_id: string | null;
  affected_item_id: string | null;
  decision_item_id: string | null;
  status: string;
  created_at: string | null;
}

export interface DirectiveListResponse {
  directives: DirectiveDetail[];
  total: number;
  pending_by_source: Record<string, number>;
}

// ─── API Functions ──────────────────────────────────────────────

/**
 * Resolve a conflict by choosing a value.
 * Creates a decision item and spawns directives for the non-chosen source.
 */
export async function resolveConflict(
  conflictItemId: string,
  request: ConflictResolveRequest,
): Promise<ConflictResolveResponse> {
  return apiPost<ConflictResolveResponse>(
    `/v1/items/${conflictItemId}/resolve`,
    request,
  );
}

/**
 * Manually fulfill a directive.
 * Typically auto-fulfilled by the import pipeline (D-10).
 */
export async function fulfillDirective(
  directiveId: string,
): Promise<DirectiveFulfillResponse> {
  return apiPost<DirectiveFulfillResponse>(
    `/v1/items/${directiveId}/fulfill`,
    {},
  );
}

/**
 * Batch resolve multiple conflicts with partial failure support.
 */
export async function bulkResolve(
  request: BulkResolveRequest,
): Promise<BulkResolveResponse> {
  return apiPost<BulkResolveResponse>(
    `/v1/action-items/bulk-resolve`,
    request,
  );
}

/**
 * Fetch pending action item rollup with counts and breakdowns.
 */
export async function getActionItems(
  projectId?: string,
): Promise<ActionItemRollup> {
  const params = projectId ? `?project=${projectId}` : "";
  return apiGet<ActionItemRollup>(`/v1/action-items${params}`);
}

/**
 * Fetch directives with optional filtering.
 */
export async function getDirectives(filters?: {
  source_id?: string;
  property_name?: string;
  status?: string;
}): Promise<DirectiveListResponse> {
  const params = new URLSearchParams();
  if (filters?.source_id) params.set("source_id", filters.source_id);
  if (filters?.property_name) params.set("property_name", filters.property_name);
  if (filters?.status) params.set("status", filters.status);
  const qs = params.toString();
  return apiGet<DirectiveListResponse>(`/v1/directives${qs ? `?${qs}` : ""}`);
}
