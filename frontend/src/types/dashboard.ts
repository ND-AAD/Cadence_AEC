// ─── Dashboard API Types ──────────────────────────────────────────
// TypeScript interfaces mirroring backend/app/schemas/dashboard.py.
// WP-13a: Project health, import summary, temporal trend, directive status.

// ─── Project Health ──────────────────────────────────────────────

/** Counts of action items by status category. */
export interface ActionItemCounts {
  unresolved_changes: number;
  unresolved_conflicts: number;
  pending_directives: number;
  fulfilled_directives: number;
  decisions_made: number;
}

/** Action item counts for a single property. */
export interface PropertyBreakdown {
  changes: number;
  conflicts: number;
  directives: number;
}

/** Conflict counts for a specific source pair. */
export interface SourcePairBreakdown {
  conflicts: number;
}

/** GET /api/v1/dashboard/health response. */
export interface ProjectHealthResponse {
  total_items: number;
  by_type: Record<string, number>;
  action_items: ActionItemCounts;
  by_property: Record<string, PropertyBreakdown>;
  by_source_pair: Record<string, SourcePairBreakdown>;
  by_affected_type: Record<string, { changes: number; conflicts: number; directives: number }>;
}

// ─── Import Summary ──────────────────────────────────────────────

/** Per-source breakdown within an import summary. */
export interface SourceImportDetail {
  source_id: string;
  source_identifier: string | null;
  source_type: string | null;
  changes: number;
  affected_items: number;
  conflicts: number;
}

/** GET /api/v1/dashboard/import-summary response. */
export interface ImportSummaryResponse {
  batch_id: string | null;
  batch_identifier: string | null;
  source_id: string | null;
  source_identifier: string | null;
  context_id: string | null;
  context_identifier: string | null;
  imported_at: string | null;
  source_changes: number;
  affected_items: number;
  new_conflicts: number;
  resolved_conflicts: number;
  directives_fulfilled: number;
  items_imported: number;
  by_source: SourceImportDetail[];
}

// ─── Temporal Trend ──────────────────────────────────────────────

/** Action item counts at a single milestone. */
export interface MilestoneTrend {
  context_id: string;
  context_identifier: string | null;
  ordinal: number;
  changes: number;
  conflicts: number;
  directives: number;
  resolved_conflicts: number;
  fulfilled_directives: number;
}

/** GET /api/v1/dashboard/temporal-trend response. */
export interface TemporalTrendResponse {
  milestones: MilestoneTrend[];
}

// ─── Directive Status ────────────────────────────────────────────

/** Directive status for a single target source. */
export interface SourceDirectiveRollup {
  source_id: string;
  source_identifier: string | null;
  pending: number;
  fulfilled: number;
}

/** GET /api/v1/dashboard/directive-status response. */
export interface DirectiveStatusResponse {
  total_pending: number;
  total_fulfilled: number;
  by_source: SourceDirectiveRollup[];
}

// ─── Dock Tree Types ─────────────────────────────────────────────

/** Instance-level item in the dock tree (level 3). */
export interface DockInstance {
  id: string;
  identifier: string;
  /** Optional property name for display (e.g., "finish", "material"). */
  propertyName?: string;
}

/** A level-2 group within a dock category (type, source, or property). */
export interface DockTypeGroup {
  key: string;
  label: string;
  count: number;
  /** Item IDs in this group (for navigation). Populated when backend provides them. */
  itemIds?: string[];
  /** Instance-level items (level 3). Populated from affected items data. */
  instances?: DockInstance[];
}

/** A top-level category in the exec summary dock tree. */
export interface DockCategory {
  key: string;
  label: string;
  count: number;
  colorClass: "redline" | "pencil" | "overlay" | "stamp" | "trace";
  defaultExpanded: boolean;
  groups: DockTypeGroup[];
}

// ─── Affected Items (Workflow Perspective) ───────────────

/** Per-item action counts for workflow categories. */
export interface ItemActionCounts {
  changes: number;
  conflicts: number;
  directives: number;
}

/** Summary of a spatial item with its action counts. */
export interface AffectedItemSummary {
  id: string;
  identifier: string | null;
  item_type: string;
  action_counts: ItemActionCounts;
}

/** Group of affected items by type. */
export interface AffectedItemGroup {
  item_type: string;
  label: string;
  count: number;
  items: AffectedItemSummary[];
}

/** GET /api/v1/dashboard/affected-items response. */
export interface AffectedItemsResponse {
  groups: AffectedItemGroup[];
}
