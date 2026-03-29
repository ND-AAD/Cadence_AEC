// ─── Comparison API ───────────────────────────────────────────────
// POST /api/v1/compare — temporal comparison across milestones.
// FE-2: Core data source for comparison mode.

import { apiPost } from "./client";

// ─── Request Types ───────────────────────────────────────────────

export interface ComparisonRequest {
  /** Specific item IDs to compare (option A). */
  item_ids?: string[];
  /** Compare all children of this parent (option B). */
  parent_item_id?: string;
  /** Earlier milestone context. */
  from_context_id: string;
  /** Later milestone context. */
  to_context_id: string;
  /** Optional: filter to a specific source. */
  source_filter?: string;
  /** Value mode: "cumulative" (carry-forward) or "submitted" (strict context match). */
  mode?: string;
  /** Pagination. */
  limit?: number;
  offset?: number;
}

// ─── Response Types ──────────────────────────────────────────────

export interface PropertyChange {
  property_name: string;
  old_value: unknown;
  new_value: unknown;
  from_context: string;
  to_context: string;
  source: string | null;
}

export interface ItemComparison {
  item_id: string;
  identifier: string | null;
  item_type: string;
  category: "added" | "removed" | "modified" | "unchanged";
  changes: PropertyChange[];
}

export interface ComparisonSummary {
  added: number;
  removed: number;
  modified: number;
  unchanged: number;
  total: number;
}

export interface ComparisonResponse {
  from_context: { id: string; identifier: string | null };
  to_context: { id: string; identifier: string | null };
  items: ItemComparison[];
  summary: ComparisonSummary;
  limit: number;
  offset: number;
}

// ─── API Function ────────────────────────────────────────────────

/**
 * Compare items across two milestone contexts.
 * Returns per-item, per-property change data.
 */
export async function postCompare(
  request: ComparisonRequest,
): Promise<ComparisonResponse> {
  return apiPost<ComparisonResponse>("/v1/compare", request);
}
