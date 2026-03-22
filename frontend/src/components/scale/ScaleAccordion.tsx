// ─── Scale Accordion ──────────────────────────────────────────────
// Container for all type groups in the scale panel.
// DS-1 §4: Connected items grouped by type, collapsible.
// Multiple groups can be expanded simultaneously.
// Click Narrative: At project level, group headers are category-level
// selection targets. Click a category → main area shows that type.

import { useState, useCallback } from "react";
import type { ConnectedGroup, TypeConfigEntry } from "@/types/navigation";
import { ScaleGroup } from "./ScaleGroup";

interface ScaleAccordionProps {
  groups: ConnectedGroup[];
  /** Type lookup for render mode awareness. */
  getType?: (typeName: string) => TypeConfigEntry | undefined;
  /** SELECT callback — shows item detail in main area without navigating. */
  onSelect: (itemId: string) => void;
  /** Currently selected item ID (for highlight). */
  selectedItemId?: string | null;
  /** Category-level selection callback. When provided, group headers
   *  act as selection targets (click header → select that type). */
  onSelectGroup?: (itemType: string) => void;
  /** Currently selected group type (for highlight). */
  selectedGroupType?: string | null;
  /** Whether comparison mode is active (drives pip filled state). */
  comparisonActive?: boolean;
}

export function ScaleAccordion({
  groups,
  getType,
  onSelect,
  selectedItemId,
  onSelectGroup,
  selectedGroupType,
  comparisonActive = false,
}: ScaleAccordionProps) {
  // Track which groups are expanded. First group defaults to expanded.
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    if (groups.length > 0) {
      initial.add(groups[0].item_type);
    }
    return initial;
  });

  const toggleGroup = useCallback((itemType: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(itemType)) {
        next.delete(itemType);
      } else {
        next.add(itemType);
      }
      return next;
    });
  }, []);

  const handleGroupHeaderClick = useCallback((itemType: string) => {
    if (onSelectGroup) {
      // Category-level selection: clicking header selects the group type.
      onSelectGroup(itemType);
    } else {
      // Default: clicking header toggles expand/collapse.
      toggleGroup(itemType);
    }
  }, [onSelectGroup, toggleGroup]);

  if (groups.length === 0) {
    return (
      <div className="px-3 py-4 text-xs text-trace">
        No connected items.
      </div>
    );
  }

  return (
    <div>
      {groups.map((group) => (
        <ScaleGroup
          key={group.item_type}
          group={group}
          renderMode={getType?.(group.item_type)?.render_mode}
          expanded={expandedGroups.has(group.item_type)}
          onToggle={() => handleGroupHeaderClick(group.item_type)}
          onChevronToggle={onSelectGroup ? () => toggleGroup(group.item_type) : undefined}
          onSelect={onSelect}
          selectedItemId={selectedItemId}
          selected={group.item_type === selectedGroupType}
          comparisonActive={comparisonActive}
        />
      ))}
    </div>
  );
}
