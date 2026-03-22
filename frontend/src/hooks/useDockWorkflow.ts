// ─── useDockWorkflow Hook ─────────────────────────────────────────
// Transforms action items + directives API data into the WorkflowTree
// structure for the exec summary dock.
//
// DS-2 §10: Three-level tree structure.
// Conflicts/Changes: grouped by item type
// Directives: grouped by target source

import { useMemo } from "react";
import type { ActionItemRollup } from "@/api/actionItems";
import type { DirectiveListResponse } from "@/api/actionItems";
import type { WorkflowCategory } from "@/components/dock/WorkflowTree";

export function useDockWorkflow(
  rollup: ActionItemRollup | null,
  directives: DirectiveListResponse | null,
): WorkflowCategory[] {
  return useMemo(() => {
    if (!rollup) return [];

    const categories: WorkflowCategory[] = [];

    // ── Conflicts ──
    if (rollup.conflicts_pending > 0) {
      categories.push({
        key: "conflicts",
        label: "Conflicts",
        colorClass: "text-redline",
        borderClass: "border-l-redline",
        count: rollup.conflicts_pending,
        groups: buildGroupsFromByType(rollup.by_type, "conflicts"),
      });
    }

    // ── Changes ──
    if (rollup.changes_pending > 0) {
      categories.push({
        key: "changes",
        label: "Changes",
        colorClass: "text-pencil",
        borderClass: "border-l-pencil",
        count: rollup.changes_pending,
        groups: buildGroupsFromByType(rollup.by_type, "changes"),
      });
    }

    // ── Directives ──
    if (rollup.directives_pending > 0) {
      categories.push({
        key: "directives",
        label: "Directives",
        colorClass: "text-overlay",
        borderClass: "border-l-overlay",
        count: rollup.directives_pending,
        groups: directives
          ? buildDirectiveGroups(directives)
          : [{ typeName: "All", count: rollup.directives_pending, instances: [] }],
      });
    }

    // ── Resolved (collapsed by default) ──
    // TODO: When backend provides resolved counts, add this category.

    // ── Notes (collapsed by default) ──
    // TODO: When notes/cairns API exists, add this category.

    return categories;
  }, [rollup, directives]);
}

/** Build type groups from the by_type breakdown. */
function buildGroupsFromByType(
  byType: Record<string, number>,
  _category: string,
) {
  // The by_type dict has keys like "changes", "conflicts", "directives".
  // For now, we create a single "All" group.
  // TODO: When backend provides by-item-type breakdowns, create real groups.
  return Object.entries(byType)
    .filter(([, count]) => count > 0)
    .map(([typeName, count]) => ({
      typeName: typeName.charAt(0).toUpperCase() + typeName.slice(1),
      count,
      instances: [], // TODO: Populate with real instance data.
    }));
}

/** Build directive groups from the directive list response. */
function buildDirectiveGroups(directives: DirectiveListResponse) {
  // Group by target source.
  const bySource = new Map<string, typeof directives.directives>();
  for (const d of directives.directives) {
    const key = d.target_source_id ?? "unknown";
    if (!bySource.has(key)) bySource.set(key, []);
    bySource.get(key)!.push(d);
  }

  return Array.from(bySource.entries()).map(([sourceId, items]) => ({
    typeName: sourceId, // TODO: Resolve source name from ID.
    count: items.length,
    instances: items.slice(0, 5).map((d) => ({
      id: d.id,
      label: d.identifier ?? d.id.slice(0, 8),
      propertyName: d.property_name,
    })),
  }));
}
