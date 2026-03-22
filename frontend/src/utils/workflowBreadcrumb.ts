// ─── Workflow Breadcrumb Encoding ─────────────────────────────────
// Format workflow item identifiers for breadcrumb display.
//
// DS-2 breadcrumb encoding:
//   Conflict: "Property: Source A ↔ Source B"
//   Change:   "Property: Context A → Context B"
//   Directive: "Property → Target Source"
//
// Raw identifiers follow the pattern set by conflict_detection.py:
//   Conflict: "{item} / {property} / {sourceA_prefix}+{sourceB_prefix}"
//   Change:   "{source} / {item} / {fromContext}→{toContext}"
//   Directive: "{item} / {property} / {targetSource} update needed"
//
// This function extracts the segments and reformats for display.
// Falls back to the raw identifier if parsing fails.

/**
 * Format a workflow item's identifier for breadcrumb display.
 *
 * Prefers structured properties when available (more reliable than parsing).
 * Falls back to parsing the raw identifier string.
 */
export function formatWorkflowBreadcrumb(
  itemType: string,
  identifier: string,
  properties?: Record<string, unknown>,
): string {
  // Prefer structured properties when available (more reliable than parsing).
  if (properties) {
    const propName = (properties.property_name ?? properties.property_path) as
      | string
      | undefined;

    if (itemType === "conflict" && propName) {
      const sourceA = properties.source_a_name as string | undefined;
      const sourceB = properties.source_b_name as string | undefined;
      if (sourceA && sourceB) {
        return `${formatPropertyLabel(propName)}: ${sourceA} ↔ ${sourceB}`;
      }
      return formatPropertyLabel(propName);
    }

    if (itemType === "change" && propName) {
      const fromCtx = properties.from_context_name as string | undefined;
      const toCtx = properties.to_context_name as string | undefined;
      if (fromCtx && toCtx) {
        return `${formatPropertyLabel(propName)}: ${fromCtx} → ${toCtx}`;
      }
      return formatPropertyLabel(propName);
    }

    if (itemType === "directive" && propName) {
      const targetSource = properties.target_source_name as string | undefined;
      if (targetSource) {
        return `${formatPropertyLabel(propName)} → ${targetSource}`;
      }
      return formatPropertyLabel(propName);
    }
  }

  // Fallback: parse the raw identifier.
  const segments = identifier.split(" / ");
  if (segments.length >= 2) {
    // Return everything after the first segment (which is the item name,
    // already represented by the parent in the breadcrumb).
    return segments.slice(1).join(" / ");
  }

  return identifier;
}

/** Convert snake_case property name to Title Case. */
function formatPropertyLabel(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
