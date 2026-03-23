// ─── Display Name Utility ─────────────────────────────────────────
// Single source of truth for how item identifiers render in the UI.
// Handles backward compatibility: property items created before the
// backend fix may still have "door/fire_rating" as their identifier
// instead of "Fire Rating".

/**
 * Get the display name for an item.
 *
 * Backward compat: if a property item still has a path-style
 * identifier (parent/name), extract and humanize the name part.
 * New property items have the label as their identifier directly.
 */
export function itemDisplayName(
  identifier: string | null,
  itemType: string,
): string {
  const id = identifier ?? itemType;

  // Backward compat for property items with path identifiers.
  if (itemType === "property" && id.includes("/")) {
    const propName = id.split("/").pop() ?? id;
    return propName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  return id;
}
