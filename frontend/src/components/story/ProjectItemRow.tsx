// ─── Project Item Row ─────────────────────────────────────────────
// An item row for the project-level data listing.
// Click = Powers of Ten zoom (navigate to the item).
// Chevron = independent toggle for inline content expansion.
// Forward arrow appears on hover per system.md connection row spec.
// Breadcrumb items are filtered upstream — every item here is forward nav.

import type { ItemSummary } from "@/types/navigation";
import { IndicatorLane } from "./IndicatorLane";
import { InlineItemPreview } from "./InlineItemPreview";
import { buildPips, presentCategories } from "@/utils/buildPips";
import { itemDisplayName } from "@/utils/displayName";

interface ProjectItemRowProps {
  item: ItemSummary;
  /** Type label (e.g., "door", "schedule"). */
  typeLabel: string;
  /** Whether comparison mode is active (drives pip filled state). */
  comparisonActive?: boolean;
  /** Navigation callback — triggers ZOOM (Powers of Ten). */
  onNavigate: (itemId: string) => void;
  /** Whether this item's inline content is expanded. */
  expanded?: boolean;
  /** Callback to toggle expand/collapse. */
  onToggle?: () => void;
  /** Breadcrumb IDs to pass through for inline preview filtering. */
  breadcrumbIds?: Set<string>;
}

export function ProjectItemRow({
  item,
  typeLabel,
  comparisonActive = false,
  onNavigate,
  expanded = false,
  onToggle,
  breadcrumbIds,
}: ProjectItemRowProps) {
  const name = itemDisplayName(item.identifier, item.item_type);
  const pips = buildPips(item.action_counts, presentCategories(comparisonActive));

  const handleChevronClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onToggle?.();
  };

  return (
    <>
      <div className="w-full text-left grid grid-cols-[120px_1fr_28px_28px] gap-x-3 items-center px-4 min-h-[34px] py-[7px] text-sm transition-colors duration-150 hover:bg-board/40 group">
        {/* Navigation button — main content area */}
        <button
          type="button"
          onClick={() => onNavigate(item.id)}
          className="col-span-2 text-left flex items-center gap-2 cursor-pointer focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-[-2px]"
        >
          <span className="text-graphite text-xs leading-[20px] truncate">
            {typeLabel}
          </span>

          <div className="min-w-0 flex items-center gap-2">
            <span className="font-mono text-ink">{name}</span>
          </div>
        </button>

        {/* Chevron button — independent expand/collapse */}
        {onToggle && (
          <button
            type="button"
            onClick={handleChevronClick}
            className="flex items-center justify-center cursor-pointer focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-[-2px]"
          >
            <svg
              className={`w-3.5 h-3.5 shrink-0 text-trace transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
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
        )}

        {/* Indicator lane — pips (IndicatorLane is quiet-aware via context) */}
        {pips.length > 0 ? (
          <IndicatorLane pips={pips} />
        ) : (
          <div />
        )}
      </div>

      {/* Expandable inline content */}
      {onToggle && (
        <div
          className="grid transition-[grid-template-rows] duration-150 ease-out"
          style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
        >
          <div className="overflow-hidden">
            <InlineItemPreview itemId={item.id} expanded={expanded} onNavigate={onNavigate} breadcrumbIds={breadcrumbIds} />
          </div>
        </div>
      )}
    </>
  );
}
