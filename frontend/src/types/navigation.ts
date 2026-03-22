// ─── Navigation Types ─────────────────────────────────────────────
// Shared TypeScript interfaces for breadcrumb, navigation state, and API contracts.

/** A single item in the breadcrumb path. */
export interface BreadcrumbItem {
  id: string;
  name: string;
  itemType: string;
}

/** Fork state for Z-axis lateral jumps. */
export interface ForkState {
  /** Shared path segments before the fork point. */
  stem: BreadcrumbItem[];
  /** Active branch (on top) — the path the user took after the lateral jump. */
  active: BreadcrumbItem[];
  /** Inactive/dead branch (below) — the path before the lateral jump. */
  inactive: BreadcrumbItem[];
}

/** Full navigation state managed by the reducer. */
export interface NavigationState {
  /** Current linear breadcrumb path (when no fork is active). */
  breadcrumb: BreadcrumbItem[];
  /** Fork state for Z-axis jumps; null when breadcrumb is linear. */
  fork: ForkState | null;
  /** True while a navigation API call is in flight. */
  pending: boolean;
  /** Error message from the last failed navigation, or null. */
  error: string | null;
  /** The action type from the last successful navigation. */
  lastAction: "push" | "bounce_back" | "no_path" | null;
}

// ─── API Contracts ────────────────────────────────────────────────

/** POST /api/navigate request body. */
export interface NavigateRequest {
  breadcrumb: string[];
  target: string;
}

/** POST /api/navigate response body. */
export interface NavigateResponse {
  breadcrumb: string[];
  action: "push" | "bounce_back" | "no_path";
  bounced_from: string | null;
}

/** GET /api/items/:id response body. */
export interface ItemResponse {
  id: string;
  item_type: string;
  identifier: string | null;
  properties: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Connected Items (GET /api/items/:id/connected) ──────────────

/** Compact item representation in connected groups. */
export interface ItemSummary {
  id: string;
  item_type: string;
  identifier: string | null;
  action_counts: {
    changes: number;
    conflicts: number;
    directives: number;
  };
}

/** A group of connected items sharing the same type. */
export interface ConnectedGroup {
  item_type: string;
  label: string;
  count: number;
  items: ItemSummary[];
}

/** GET /api/items/:id/connected response body. */
export interface ConnectedItemsResponse {
  item: ItemResponse;
  connected: ConnectedGroup[];
}

// ─── Render Modes ────────────────────────────────────────────────

/** How items of a type render in collections (DS-1 §5.2). */
export type RenderMode = "table" | "cards" | "list" | "timeline";

// ─── Type Registry (GET /api/items/types) ─────────────────────────

/** A property definition within a type config. */
export interface TypePropertyDef {
  name: string;
  label: string;
  data_type: string;
  required: boolean;
  unit: string | null;
}

/** Configuration for a single item type. */
export interface TypeConfigEntry {
  label: string;
  plural_label: string;
  category: string;
  icon: string;
  color: string;
  navigable: boolean;
  is_source_type: boolean;
  is_context_type: boolean;
  render_mode: RenderMode;
  default_sort: string;
  valid_targets: string[];
  properties: TypePropertyDef[];
}

/** GET /api/items/types response body: map of type name → config. */
export type TypeRegistryResponse = Record<string, TypeConfigEntry>;

// ─── Reducer Actions ──────────────────────────────────────────────

export type NavigationAction =
  | { type: "NAVIGATE_START" }
  | { type: "NAVIGATE_SUCCESS"; breadcrumb: BreadcrumbItem[]; action: NavigateResponse["action"]; bouncedFrom: string | null }
  | { type: "NAVIGATE_ERROR"; error: string }
  | { type: "SET_BREADCRUMB"; breadcrumb: BreadcrumbItem[] }
  | { type: "POP_TO"; index: number }
  | { type: "FORK_CREATE"; stem: BreadcrumbItem[]; active: BreadcrumbItem[]; inactive: BreadcrumbItem[] }
  | { type: "FORK_ABSORB"; breadcrumb: BreadcrumbItem[] };
