// ─── List Renderer ────────────────────────────────────────────────
// Default render mode: collapsible group of navigable item rows.
// Uses the same ProjectItemRow as the project-level listing so
// behavior is identical at every scale: click = navigate, chevron =
// expand inline preview.

import { useState, useCallback } from "react";
import type { ConnectedGroup, TypeConfigEntry } from "@/types/navigation";
import { excludeBreadcrumbItems } from "@/utils/groupFilters";
import { CollapsibleGroupHeader } from "../CollapsibleGroupHeader";
import { ProjectItemRow } from "../ProjectItemRow";

export interface RendererProps {
  group: ConnectedGroup;
  typeConfig?: TypeConfigEntry;
  breadcrumbIds: Set<string>;
  onNavigate: (itemId: string) => void;
  /** Whether comparison mode is active (drives pip filled state). */
  comparisonActive?: boolean;
}

export function ListRenderer({
  group,
  typeConfig,
  breadcrumbIds,
  onNavigate,
  comparisonActive = false,
}: RendererProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  const toggleItem = useCallback((itemId: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }, []);

  // Filter out breadcrumb items — they're accessible via snap-back.
  const filtered = excludeBreadcrumbItems([group], breadcrumbIds);
  if (filtered.length === 0) return null;
  const filteredGroup = filtered[0];

  const typeLabel = typeConfig?.label ?? group.item_type;

  return (
    <div>
      <CollapsibleGroupHeader
        label={filteredGroup.label}
        count={filteredGroup.count}
        expanded={!collapsed}
        onToggle={() => setCollapsed((c) => !c)}
      />

      <div
        className="grid transition-[grid-template-rows] duration-150 ease-out"
        style={{ gridTemplateRows: collapsed ? "0fr" : "1fr" }}
      >
        <div className="overflow-hidden">
          <div className="divide-y divide-rule/50">
            {filteredGroup.items.map((item) => (
              <ProjectItemRow
                key={item.id}
                item={item}
                typeLabel={typeLabel}
                comparisonActive={comparisonActive}
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
