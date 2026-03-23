// ─── useDockCategories Hook ───────────────────────────────────────
// Transforms raw dashboard API data into the three-level tree structure
// rendered by the exec summary dock.
//
// Categories: Conflicts, Changes, Directives, Resolved, Notes.
// Each category has a level-2 breakdown (type groups) derived from
// the available API data.

import { useMemo } from "react";
import type {
  ProjectHealthResponse,
  DirectiveStatusResponse,
  AffectedItemsResponse,
  DockCategory,
  DockTypeGroup,
  DockInstance,
} from "@/types/dashboard";
import { useTypeRegistry } from "@/hooks/useTypeRegistry";

/**
 * Capitalize and pluralize a type name for display.
 * E.g., "door" → "Doors", "hardware_set" → "Hardware Sets"
 */
function getDisplayLabel(typeName: string, pluralLabel?: string): string {
  // If we have a plural label from type config, use it
  if (pluralLabel) {
    return pluralLabel;
  }

  // Fallback: simple capitalize + pluralize
  // Replace underscores with spaces, capitalize each word, add 's'
  const words = typeName.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1));
  return words.join(" ") + "s";
}

/**
 * Build the dock category tree from dashboard health + directive status data.
 *
 * Returns an empty array if health data is not yet available.
 */
export function useDockCategories(
  health: ProjectHealthResponse | null,
  directiveStatus: DirectiveStatusResponse | null,
  affectedItems?: AffectedItemsResponse | null,
): DockCategory[] {
  const { getType } = useTypeRegistry();

  return useMemo(() => {
    if (!health) return [];

    // Build instance lookup from affected items (level 3 data).
    // Maps: category → item_type → DockInstance[]
    const instanceMap: Record<string, Record<string, DockInstance[]>> = {
      conflicts: {},
      changes: {},
      directives: {},
    };
    if (affectedItems) {
      for (const group of affectedItems.groups) {
        for (const item of group.items) {
          for (const category of ["conflicts", "changes", "directives"] as const) {
            if (item.action_counts[category] > 0) {
              const bucket = instanceMap[category];
              if (!bucket[group.item_type]) bucket[group.item_type] = [];
              bucket[group.item_type].push({
                id: item.id,
                identifier: item.identifier ?? item.item_type,
              });
            }
          }
        }
      }
    }

    const categories: DockCategory[] = [];

    // ─── Conflicts ─────────────────────────────────────────────
    // Level 2: breakdown by affected item type.
    const conflictGroups: DockTypeGroup[] = Object.entries(health.by_affected_type)
      .filter(([, v]) => v.conflicts > 0)
      .map(([typeName, v]) => {
        const typeConfig = getType(typeName);
        return {
          key: typeName,
          label: getDisplayLabel(typeName, typeConfig?.plural_label),
          count: v.conflicts,
          instances: instanceMap.conflicts[typeName],
        };
      })
      .sort((a, b) => b.count - a.count);

    if (health.action_items.unresolved_conflicts > 0 || conflictGroups.length > 0) {
      categories.push({
        key: "conflicts",
        label: "Conflicts",
        count: health.action_items.unresolved_conflicts,
        colorClass: "redline",
        defaultExpanded: true,
        groups: conflictGroups,
      });
    }

    // ─── Changes ───────────────────────────────────────────────
    // Level 2: breakdown by affected item type.
    const changeGroups: DockTypeGroup[] = Object.entries(health.by_affected_type)
      .filter(([, v]) => v.changes > 0)
      .map(([typeName, v]) => {
        const typeConfig = getType(typeName);
        return {
          key: typeName,
          label: getDisplayLabel(typeName, typeConfig?.plural_label),
          count: v.changes,
          instances: instanceMap.changes[typeName],
        };
      })
      .sort((a, b) => b.count - a.count);

    if (health.action_items.unresolved_changes > 0 || changeGroups.length > 0) {
      categories.push({
        key: "changes",
        label: "Changes",
        count: health.action_items.unresolved_changes,
        colorClass: "pencil",
        defaultExpanded: true,
        groups: changeGroups,
      });
    }

    // ─── Directives ────────────────────────────────────────────
    // Level 2: breakdown by affected item type.
    const directiveGroups: DockTypeGroup[] = Object.entries(health.by_affected_type)
      .filter(([, v]) => v.directives > 0)
      .map(([typeName, v]) => {
        const typeConfig = getType(typeName);
        return {
          key: typeName,
          label: getDisplayLabel(typeName, typeConfig?.plural_label),
          count: v.directives,
          instances: instanceMap.directives[typeName],
        };
      })
      .sort((a, b) => b.count - a.count);

    const totalDirectives =
      health.action_items.pending_directives +
      health.action_items.fulfilled_directives;

    if (totalDirectives > 0 || directiveGroups.length > 0) {
      categories.push({
        key: "directives",
        label: "Directives",
        count: totalDirectives,
        colorClass: "overlay",
        defaultExpanded: true,
        groups: directiveGroups,
      });
    }

    // ─── Resolved ──────────────────────────────────────────────
    // Collapsed by default; no level-2 breakdown yet.
    if (health.action_items.decisions_made > 0) {
      categories.push({
        key: "resolved",
        label: "Resolved",
        count: health.action_items.decisions_made,
        colorClass: "stamp",
        defaultExpanded: false,
        groups: [],
      });
    }

    // ─── Notes (placeholder) ───────────────────────────────────
    // Notes backend is not yet built; show placeholder category.
    categories.push({
      key: "notes",
      label: "Notes",
      count: 0,
      colorClass: "trace",
      defaultExpanded: false,
      groups: [],
    });

    return categories;
  }, [health, directiveStatus, affectedItems, getType]);
}
