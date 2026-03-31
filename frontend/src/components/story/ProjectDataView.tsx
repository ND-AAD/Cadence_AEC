// ─── Project Data View ────────────────────────────────────────────
// Project-level main area content. Renders filtered data groups as
// collapsible sections with navigable item rows.
// Click = page turn (Powers of Ten zoom). Forward arrow on hover.
// When a category is selected in the left panel, only that type's
// items are shown.

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import type { ConnectedGroup, TypeConfigEntry } from "@/types/navigation";
import type { AffectedItemsResponse } from "@/types/dashboard";
import { excludeBreadcrumbItems } from "@/utils/groupFilters";
import { CollapsibleGroupHeader } from "./CollapsibleGroupHeader";
import { ProjectItemRow } from "./ProjectItemRow";

interface ProjectDataViewProps {
  /** Data groups (already filtered to exclude workflow/hidden types). */
  groups: ConnectedGroup[];
  /** All connected groups including workflow items (for workflow perspective). */
  allConnectedGroups?: ConnectedGroup[];
  /** Affected items for workflow perspective (from backend traversal). */
  affectedItems?: AffectedItemsResponse | null;
  /** Type config lookup. */
  getType: (typeName: string) => TypeConfigEntry | undefined;
  /** Set of breadcrumb item IDs for in-path detection. */
  breadcrumbIds: Set<string>;
  /** Navigation callback (zoom = main area click). */
  onNavigate: (itemId: string) => void;
  /** Whether comparison mode is active (drives pip filled state). */
  comparisonActive?: boolean;
  /** When set, only show items of this type (category-level selection from left panel). */
  selectedGroupType?: string | null;
  /** When set, show items filtered by workflow category and grouped by type. */
  workflowPerspective?: {
    category: string;    // "changes", "conflicts", "directives"
    groupKey: string;    // item_type like "door", "hardware_set"
    groupLabel: string;  // display label like "Doors"
  } | null;
  /** Item selected from the dashboard (left panel). Drives expand-in-place. */
  selectedItemId?: string | null;
  /** Whether Quiet mode is active. Filters out milestone groups. */
  isQuiet?: boolean;
  /** Comparison categories for child items (from bulk parent comparison). */
  comparisonCategoryMap?: Map<string, "added" | "removed" | "modified" | "unchanged">;
}

export function ProjectDataView({
  groups,
  allConnectedGroups,
  affectedItems,
  getType,
  breadcrumbIds,
  onNavigate,
  comparisonActive = false,
  selectedGroupType,
  workflowPerspective,
  selectedItemId,
  isQuiet = false,
  comparisonCategoryMap,
}: ProjectDataViewProps) {
  // All sections default to expanded.
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  // For workflow perspective: track collapsed workflow categories
  const [collapsedWorkflowCategories, setCollapsedWorkflowCategories] = useState<
    Set<string>
  >(new Set());
  // Track expanded items for inline content preview
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  const toggleGroup = useCallback((itemType: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(itemType)) {
        next.delete(itemType);
      } else {
        next.add(itemType);
      }
      return next;
    });
  }, []);

  const toggleWorkflowCategory = useCallback((category: string) => {
    setCollapsedWorkflowCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  }, []);

  const toggleItem = useCallback((itemId: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }, []);

  // Ref for scrolling to the selected item
  const selectedRef = useRef<HTMLDivElement>(null);

  // Exclude breadcrumb items, then filter to selected category.
  const filteredGroups = useMemo(
    () => excludeBreadcrumbItems(groups, breadcrumbIds),
    [groups, breadcrumbIds],
  );

  const visibleGroups = useMemo(() => {
    let groups = filteredGroups;
    // In Quiet mode, milestones disappear from the project view.
    if (isQuiet) {
      groups = groups.filter((g) => g.item_type !== "milestone" && g.item_type !== "issuance");
    }
    if (selectedGroupType) {
      groups = groups.filter((g) => g.item_type === selectedGroupType);
    }
    return groups;
  }, [filteredGroups, selectedGroupType, isQuiet]);

  // When dashboard selection changes, expand that item and scroll to it.
  // Also ensure its parent group is not collapsed.
  useEffect(() => {
    if (!selectedItemId) return;

    // Expand the selected item
    setExpandedItems(new Set([selectedItemId]));

    // Find which group contains this item and ensure it's not collapsed
    const containingGroup = filteredGroups.find((g) =>
      g.items.some((item) => item.id === selectedItemId)
    );
    if (containingGroup) {
      setCollapsedGroups((prev) => {
        if (prev.has(containingGroup.item_type)) {
          const next = new Set(prev);
          next.delete(containingGroup.item_type);
          return next;
        }
        return prev;
      });
    }

    // Scroll to the item after expansion renders
    requestAnimationFrame(() => {
      selectedRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }, [selectedItemId, filteredGroups]);

  // Workflow perspective rendering
  const workflowSections = useMemo(() => {
    if (!workflowPerspective) return null;

    const categories = ["changes", "conflicts", "directives"];
    const sections: Record<
      string,
      { label: string; items: Map<string, { label: string; items: any[] }> }
    > = {};

    // Initialize sections
    for (const cat of categories) {
      sections[cat] = {
        label: cat.charAt(0).toUpperCase() + cat.slice(1),
        items: new Map(),
      };
    }

    // Use affectedItems if available (preferred for workflow perspective)
    // since it traverses the full project graph via backend.
    // Fall back to allConnectedGroups if affectedItems not yet loaded.
    if (affectedItems) {
      // Build from affected items (backend-traversed full graph)
      for (const group of affectedItems.groups) {
        for (const item of group.items) {
          for (const category of categories) {
            const actionCount = item.action_counts[category as keyof typeof item.action_counts];
            if (actionCount > 0) {
              const section = sections[category];
              if (!section.items.has(group.item_type)) {
                section.items.set(group.item_type, {
                  label: group.label,
                  items: [],
                });
              }
              section.items.get(group.item_type)!.items.push(item);
            }
          }
        }
      }
    } else if (allConnectedGroups) {
      // Fall back to connected groups (immediate children only)
      // Filter and group items by workflow category and type.
      for (const group of allConnectedGroups) {
        for (const item of group.items) {
          for (const category of categories) {
            const actionCount = item.action_counts[category as keyof typeof item.action_counts];
            if (actionCount > 0) {
              const section = sections[category];
              if (!section.items.has(group.item_type)) {
                const typeConfig = getType(group.item_type);
                section.items.set(group.item_type, {
                  label: typeConfig?.label ?? group.item_type,
                  items: [],
                });
              }
              section.items.get(group.item_type)!.items.push(item);
            }
          }
        }
      }
    }

    return sections;
  }, [workflowPerspective, affectedItems, allConnectedGroups, getType]);

  // Render workflow perspective if active
  if (workflowPerspective && workflowSections) {
    const categories = ["changes", "conflicts", "directives"];
    const categoryColors: Record<string, string> = {
      changes: "text-pencil-ink",
      conflicts: "text-redline-ink",
      directives: "text-overlay",
    };
    const categoryBorders: Record<string, string> = {
      changes: "border-l-pencil",
      conflicts: "border-l-redline",
      directives: "border-l-overlay",
    };

    const hasAnyItems = categories.some(
      (cat) => workflowSections[cat].items.size > 0
    );

    if (!hasAnyItems) {
      return (
        <div className="flex items-center justify-center h-full p-8">
          <p className="text-sm text-trace">No items with workflow actions.</p>
        </div>
      );
    }

    return (
      <div className="bg-sheet min-h-full divide-y divide-rule">
        {categories.map((category) => {
          const section = workflowSections[category];
          const expanded = !collapsedWorkflowCategories.has(category);
          const isSelectedCategory =
            workflowPerspective.category === category;
          const itemCount = Array.from(section.items.values()).reduce(
            (sum, typeGroup) => sum + typeGroup.items.length,
            0
          );

          if (itemCount === 0) return null;

          return (
            <div key={category} className={`border-l-2 ${categoryBorders[category]}`}>
              {/* Workflow category header */}
              <button
                type="button"
                onClick={() => toggleWorkflowCategory(category)}
                className={`w-full text-left px-4 py-1.5 flex items-center gap-2 ${categoryColors[category]} font-semibold uppercase text-sm tracking-tight hover:bg-board/40 cursor-pointer transition-colors`}
              >
                <svg
                  className={`w-3 h-3 shrink-0 transition-transform duration-150 ${
                    expanded ? "rotate-90" : ""
                  }`}
                  viewBox="0 0 14 14"
                  fill="none"
                >
                  <path
                    d="M5 3l4 4-4 4"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <span>{section.label}</span>
                <span className="text-xs text-trace ml-auto">({itemCount})</span>
              </button>

              {/* Expandable content */}
              <div
                className="grid transition-[grid-template-rows] duration-150 ease-out"
                style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
              >
                <div className="overflow-hidden">
                  {/* Type subgroups */}
                  <div className="divide-y divide-rule/30">
                    {Array.from(section.items.entries()).map(
                      ([itemType, typeGroup]) => {
                        // Selected group defaults open, others default closed.
                        // Manual toggle inverts the default.
                        const isSelected =
                          isSelectedCategory &&
                          workflowPerspective.groupKey === itemType;
                        const toggled = collapsedGroups.has(itemType);
                        const typeExpanded = isSelected ? !toggled : toggled;

                        return (
                          <div key={itemType}>
                            <CollapsibleGroupHeader
                              label={typeGroup.label}
                              count={typeGroup.items.length}
                              expanded={typeExpanded}
                              onToggle={() => toggleGroup(itemType)}
                            />

                            {/* Type items */}
                            <div
                              className="grid transition-[grid-template-rows] duration-150 ease-out"
                              style={{
                                gridTemplateRows: typeExpanded ? "1fr" : "0fr",
                              }}
                            >
                              <div className="overflow-hidden">
                                <div className="divide-y divide-rule/50">
                                  {typeGroup.items.map((item) => (
                                    <ProjectItemRow
                                      key={item.id}
                                      item={item}
                                      typeLabel={typeGroup.label}
                                      comparisonActive={comparisonActive}
                                      workflowCategory={category}
                                      comparisonCategory={comparisonCategoryMap?.get(item.id)}
                                      onNavigate={onNavigate}
                                      expanded={expandedItems.has(item.id)}
                                      onToggle={() => toggleItem(item.id)}
                                      breadcrumbIds={breadcrumbIds}
                                    />
                                  ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  if (filteredGroups.length === 0) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <p className="text-sm text-trace">No items yet.</p>
      </div>
    );
  }

  if (visibleGroups.length === 0 && selectedGroupType) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <p className="text-sm text-trace">No {selectedGroupType} items.</p>
      </div>
    );
  }

  return (
    <div className="bg-sheet min-h-full divide-y divide-rule">
      {visibleGroups.map((group) => {
        const expanded = !collapsedGroups.has(group.item_type);
        const typeConfig = getType(group.item_type);
        const typeLabel = typeConfig?.label ?? group.item_type;

        return (
          <div key={group.item_type}>
            <CollapsibleGroupHeader
              label={group.label}
              count={group.count}
              expanded={expanded}
              onToggle={() => toggleGroup(group.item_type)}
            />

            {/* Collapsible item list */}
            <div
              className="grid transition-[grid-template-rows] duration-150 ease-out"
              style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
            >
              <div className="overflow-hidden">
                <div className="divide-y divide-rule/50">
                  {group.items.map((item) => (
                    <div key={item.id} ref={item.id === selectedItemId ? selectedRef : undefined}>
                      <ProjectItemRow
                        item={item}
                        typeLabel={typeLabel}
                        comparisonActive={comparisonActive}
                        comparisonCategory={comparisonCategoryMap?.get(item.id)}
                        onNavigate={onNavigate}
                        expanded={expandedItems.has(item.id)}
                        onToggle={() => toggleItem(item.id)}
                        breadcrumbIds={breadcrumbIds}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
