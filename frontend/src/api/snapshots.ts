// ─── Snapshots API ────────────────────────────────────────────────
// Resolved property data from the snapshot engine.
// WP-FE1-B: Fetches effective property values across sources.

import { apiGet } from "./client";

/** Value mode for resolved properties. */
export type ValueMode = "cumulative" | "submitted" | "current";

/** Navigation handles for workflow items connected to a property. */
export interface PropertyWorkflowRefs {
  conflict_id: string | null;
  change_ids: string[];
  decision_id: string | null;
  directive_ids: string[];
  resolution_metadata: {
    decided_by: string | null;
    resolved_at: string | null;
    method: string | null;
    rationale: string | null;
    chosen_source: string | null;
  } | null;
}

/** A single property with its resolved status across sources. */
export interface ResolvedProperty {
  /** Property key name (e.g., "fire_rating"). Matches backend PropertyResolution.property_name. */
  property_name: string;
  /** Resolution status across sources. */
  status: "agreed" | "single_source" | "conflicted" | "resolved";
  /** The effective value (resolved or sole-source value). */
  value: unknown;
  /** Display unit (from type config), if applicable. */
  unit: string | null;
  /** Source identifier → that source's asserted value. From backend PropertyResolution.sources. */
  sources: Record<string, unknown>;
  /** Source identifier → source item UUID. From backend PropertyResolution.source_ids. */
  source_ids?: Record<string, string>;
  /** Workflow navigation handles. Null when no workflow items exist for this property. */
  workflow: PropertyWorkflowRefs | null;
  /** Milestone identifier where the value originated. Null when submitted at the viewed context. */
  effective_context: string | null;
}

/** GET /api/v1/snapshots/item/{id}/resolved response. */
export interface ResolvedPropertiesResponse {
  item_id: string;
  context_id: string;
  mode: ValueMode;
  properties: ResolvedProperty[];
}

/**
 * Fetch resolved properties for an item at a given context.
 * Returns per-property status and effective values across all sources.
 */
export async function getResolvedProperties(
  itemId: string,
  contextId: string | null,
  mode: ValueMode = "cumulative",
): Promise<ResolvedPropertiesResponse> {
  const params = new URLSearchParams({ mode });
  if (contextId) params.set("context", contextId);
  return apiGet<ResolvedPropertiesResponse>(
    `/v1/snapshots/item/${itemId}/resolved?${params.toString()}`,
  );
}
