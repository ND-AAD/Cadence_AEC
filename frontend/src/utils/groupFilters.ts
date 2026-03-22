// ─── Group Filters ────────────────────────────────────────────────
// Utility for filtering ConnectedGroup arrays by category.
// Used to separate data types (left panel) from workflow types (right panel).
// Primary filter: type config category field. Fallback: known type lists
// (covers the case where the type registry hasn't loaded yet).

import type { ConnectedGroup, TypeConfigEntry } from "@/types/navigation";

/** Internal batch types that should never appear in UI panels. */
const HIDDEN_TYPES = new Set([
  "import_batch",
  "preprocess_batch",
  "extraction_batch",
]);

/** Known workflow item types (fallback when type registry hasn't loaded). */
const WORKFLOW_TYPES = new Set([
  "change",
  "conflict",
  "decision",
  "directive",
  "note",
]);

/** Categories that belong in the data (left) panel. */
const DATA_CATEGORIES = new Set([
  "spatial",
  "document",
  "temporal",
  "organization",
  "definition",
]);

/**
 * Returns true if a group represents a data type (architecture items).
 * Uses type config category as primary check, falls back to known type lists.
 */
function isDataGroup(
  group: ConnectedGroup,
  getType: (typeName: string) => TypeConfigEntry | undefined,
): boolean {
  if (HIDDEN_TYPES.has(group.item_type)) return false;
  if (WORKFLOW_TYPES.has(group.item_type)) return false;

  const tc = getType(group.item_type);
  if (tc) {
    return DATA_CATEGORIES.has(tc.category);
  }
  // Unknown type with no config — show it (safe default for user-defined types).
  return true;
}

/**
 * Filter connected groups to only data types (spatial, document, temporal,
 * organization, definition). Excludes workflow types and hidden batch types.
 * Used for the scale (left) panel and main area connections.
 */
export function filterDataGroups(
  groups: ConnectedGroup[],
  getType: (typeName: string) => TypeConfigEntry | undefined,
): ConnectedGroup[] {
  return groups.filter((group) => isDataGroup(group, getType));
}

/**
 * Remove individual items that are already in the breadcrumb path.
 * The breadcrumb is the navigation back — showing those items as connection
 * rows is redundant. Drops groups that become empty after filtering.
 */
export function excludeBreadcrumbItems(
  groups: ConnectedGroup[],
  breadcrumbIds: Set<string>,
): ConnectedGroup[] {
  if (breadcrumbIds.size === 0) return groups;

  const filtered: ConnectedGroup[] = [];
  for (const group of groups) {
    const remaining = group.items.filter((item) => !breadcrumbIds.has(item.id));
    if (remaining.length > 0) {
      filtered.push({
        ...group,
        items: remaining,
        count: remaining.length,
      });
    }
  }
  return filtered;
}
