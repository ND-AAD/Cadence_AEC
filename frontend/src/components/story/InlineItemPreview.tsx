// ─── Inline Item Preview ───────────────────────────────────────────
// Shows a compact summary of an item's contents when its chevron is
// expanded. Visually nested (indented + left border) to distinguish
// from project-level groups. Caps item listing per group to avoid
// burying sibling rows — shows a "+ N more" link for overflow.
//
// When workflowFilter is set, only shows items that have action counts
// for the specified category (e.g., only properties with changes).
// Pips for the filtered category render filled because those items
// ARE the thing the user is looking at.

import { useState, useEffect, useCallback } from "react";
import { getConnectedItems } from "@/api/connected";
import type { ConnectedItemsResponse, ConnectedGroup, ItemSummary } from "@/types/navigation";
import { filterDataGroups, excludeBreadcrumbItems } from "@/utils/groupFilters";
import { useTypeRegistry } from "@/hooks/useTypeRegistry";
import { buildPips, presentCategories } from "@/utils/buildPips";
import { itemDisplayName } from "@/utils/displayName";
import { IndicatorLane } from "./IndicatorLane";

/** Max items shown per group before "+ N more" appears. */
const MAX_VISIBLE_ITEMS = 5;

/** Map workflow filter keys to action_counts keys. */
const WORKFLOW_ACTION_KEY: Record<string, keyof ItemSummary["action_counts"]> = {
  changes: "changes",
  conflicts: "conflicts",
  directives: "directives",
};

interface InlineItemPreviewProps {
  itemId: string;
  expanded: boolean;
  /** Navigation callback — passed through to item rows. */
  onNavigate?: (itemId: string) => void;
  /** Breadcrumb item IDs to exclude from the preview (parent items). */
  breadcrumbIds?: Set<string>;
  /** Active workflow filter. When set, only items with this action
   *  category are shown, and their pips render filled. */
  workflowFilter?: string;
}

export function InlineItemPreview({ itemId, expanded, onNavigate, breadcrumbIds, workflowFilter }: InlineItemPreviewProps) {
  const [data, setData] = useState<ConnectedItemsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [showAllGroups, setShowAllGroups] = useState<Set<string>>(new Set());
  const { getType } = useTypeRegistry();

  const toggleGroup = useCallback((itemType: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(itemType)) next.delete(itemType);
      else next.add(itemType);
      return next;
    });
  }, []);

  const toggleShowAll = useCallback((itemType: string) => {
    setShowAllGroups((prev) => {
      const next = new Set(prev);
      if (next.has(itemType)) next.delete(itemType);
      else next.add(itemType);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!expanded) return;

    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);

      try {
        const result = await getConnectedItems(itemId);
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
          setLoading(false);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [itemId, expanded]);

  if (loading) {
    return (
      <div className="ml-[68px] pl-3 border-l border-rule/50 py-2">
        <span className="text-xs text-trace animate-pulse">Loading…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ml-[68px] pl-3 border-l border-rule/50 py-2">
        <span className="text-xs text-trace">Error: {error}</span>
      </div>
    );
  }

  if (!data) return null;

  // Filter to data groups only, then exclude breadcrumb items (parents).
  const filtered = filterDataGroups(data.connected, getType);
  let dataGroups = breadcrumbIds ? excludeBreadcrumbItems(filtered, breadcrumbIds) : filtered;

  // When a workflow filter is active, only show items with that action count > 0.
  const actionKey = workflowFilter ? WORKFLOW_ACTION_KEY[workflowFilter] : undefined;
  if (actionKey) {
    dataGroups = filterGroupsByAction(dataGroups, actionKey);
  }

  // Build the present set for pip rendering.
  // When workflow filter is active, the filtered category is "present" (filled)
  // because these items ARE the thing the user is looking at.
  const present = presentCategories(false);
  if (workflowFilter) {
    present.add(workflowFilter);
  }

  if (dataGroups.length === 0) {
    return (
      <div className="ml-[68px] pl-3 border-l border-rule/50 py-2">
        <span className="text-xs text-trace">No items</span>
      </div>
    );
  }

  return (
    <div className="ml-[68px] border-l border-rule/50 py-1">
      {dataGroups.map((group) => {
        const typeConfig = getType(group.item_type);
        const typeLabel = typeConfig?.label ?? group.item_type;
        const isCollapsed = collapsedGroups.has(group.item_type);
        const showAll = showAllGroups.has(group.item_type);
        const visibleItems = showAll
          ? group.items
          : group.items.slice(0, MAX_VISIBLE_ITEMS);
        const overflowCount = group.items.length - MAX_VISIBLE_ITEMS;

        return (
          <div key={group.item_type}>
            {/* Nested group header — dual gesture: row = navigate, chevron = collapse. */}
            <div className="w-full grid grid-cols-[1fr_28px_28px] gap-x-3 items-center pr-4 min-h-[28px] hover:bg-board/40 transition-colors duration-100">
              {/* Label area — click navigates to parent item */}
              <button
                type="button"
                onClick={() => onNavigate?.(itemId)}
                className="text-left pl-3 py-1 flex items-center gap-1.5 cursor-pointer"
              >
                <span className="text-[11px] font-mono text-trace/70 uppercase tracking-wide">
                  {group.label}
                </span>
                <span className="text-[11px] text-trace/50">
                  ({group.count})
                </span>
              </button>

              {/* Chevron — click toggles collapse */}
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); toggleGroup(group.item_type); }}
                className="flex items-center justify-center cursor-pointer"
              >
                <svg
                  className={`w-3 h-3 shrink-0 text-trace/50 transition-transform duration-150 ${isCollapsed ? "" : "rotate-90"}`}
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
              </button>

              {/* Empty pip column — alignment placeholder */}
              <div />
            </div>

            {/* Collapsible item rows */}
            <div
              className="grid transition-[grid-template-rows] duration-150 ease-out"
              style={{ gridTemplateRows: isCollapsed ? "0fr" : "1fr" }}
            >
              <div className="overflow-hidden">
                <div className="divide-y divide-rule/30">
                  {visibleItems.map((item) => (
                    <InlineRow
                      key={item.id}
                      item={item}
                      typeLabel={typeLabel}
                      onNavigate={onNavigate}
                      present={present}
                    />
                  ))}
                </div>

                {/* Overflow toggle */}
                {overflowCount > 0 && (
                  <button
                    type="button"
                    onClick={() => toggleShowAll(group.item_type)}
                    className="pl-3 pr-4 py-1 text-[11px] text-trace hover:text-graphite transition-colors cursor-pointer"
                  >
                    {showAll ? "show less" : `+ ${overflowCount} more`}
                  </button>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Filter connected groups to only include items with the given action count > 0. */
function filterGroupsByAction(
  groups: ConnectedGroup[],
  actionKey: keyof ItemSummary["action_counts"],
): ConnectedGroup[] {
  const result: ConnectedGroup[] = [];
  for (const group of groups) {
    const filtered = group.items.filter(
      (item) => (item.action_counts[actionKey] ?? 0) > 0,
    );
    if (filtered.length > 0) {
      result.push({ ...group, items: filtered, count: filtered.length });
    }
  }
  return result;
}

/** Compact inline row — smaller than ProjectItemRow, no expand chevron. */
function InlineRow({
  item,
  typeLabel,
  onNavigate,
  present,
}: {
  item: ItemSummary;
  typeLabel: string;
  onNavigate?: (itemId: string) => void;
  present: Set<string>;
}) {
  const name = itemDisplayName(item.identifier, item.item_type);
  const pips = buildPips(item.action_counts, present);

  return (
    <button
      type="button"
      onClick={() => onNavigate?.(item.id)}
      className="w-full text-left grid grid-cols-[80px_1fr_28px_28px] gap-x-3 items-center pl-3 pr-4 min-h-[28px] py-1 text-xs group cursor-pointer transition-colors duration-150 hover:bg-board/40"
    >
      <span className="text-trace truncate">{typeLabel}</span>
      <span className="font-mono text-ink truncate">{name}</span>
      {/* Empty chevron column — alignment placeholder */}
      <div />
      {pips.length > 0 ? (
        <IndicatorLane pips={pips} />
      ) : (
        <div />
      )}
    </button>
  );
}
