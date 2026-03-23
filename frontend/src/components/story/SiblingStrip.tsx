// ─── Sibling Strip ────────────────────────────────────────────────
// Z-axis awareness bar below the breadcrumb, within the story panel.
// system.md: Shows items connected to the parent you arrived from.
// Active: bg-board font-medium text-ink
// Siblings: text-graphite hover:text-ink
// In-path: text-trace hover:text-graphite (snap-back)
// DS-2 §3: Pips for action count indicators.

import type { ItemSummary } from "@/types/navigation";
import { itemDisplayName } from "@/utils/displayName";
import { IndicatorLane } from "./IndicatorLane";
import { buildPips, presentCategories } from "@/utils/buildPips";

interface SiblingStripProps {
  /** Name of the parent item (e.g., "Room 203"). */
  parentName: string;
  /** All siblings (items connected to the same parent). */
  siblings: ItemSummary[];
  /** ID of the currently active item. */
  activeId: string;
  /** IDs of items in the current breadcrumb (for in-path detection). */
  breadcrumbIds: Set<string>;
  /** Navigation callback. */
  onNavigate: (itemId: string) => void;
  /** Whether comparison mode is active (drives pip filled state). */
  comparisonActive?: boolean;
}

export function SiblingStrip({
  parentName,
  siblings,
  activeId,
  breadcrumbIds,
  onNavigate,
  comparisonActive = false,
}: SiblingStripProps) {
  if (siblings.length <= 1) return null;

  return (
    <div className="px-4 py-1.5 border-b border-rule bg-vellum/60 flex items-center gap-1 text-xs overflow-x-auto">
      <span className="text-trace shrink-0">via {parentName}:</span>
      {siblings.map((sib, i) => {
        const isActive = sib.id === activeId;
        const isInPath = !isActive && breadcrumbIds.has(sib.id);
        const name = itemDisplayName(sib.identifier, sib.item_type);
        const pips = buildPips(sib.action_counts, presentCategories(comparisonActive));

        return (
          <span key={sib.id} className="flex items-center gap-1 shrink-0">
            {i > 0 && <span className="text-rule-emphasis">&middot;</span>}
            {isActive ? (
              <span className="px-1.5 py-0.5 rounded-sm bg-board font-medium text-ink">
                {name}
              </span>
            ) : (
              <button
                type="button"
                onClick={() => onNavigate(sib.id)}
                className={`px-1.5 py-0.5 rounded-sm transition-colors duration-150 ${
                  isInPath
                    ? "text-trace hover:text-graphite hover:bg-board/30 cursor-pointer"
                    : "text-graphite hover:text-ink hover:bg-board/50 cursor-pointer"
                }`}
              >
                {name}
              </button>
            )}

            {/* Indicator pips */}
            {pips.length > 0 && (
              <span className="shrink-0">
                <IndicatorLane pips={pips} />
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}
