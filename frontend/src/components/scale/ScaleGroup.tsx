// ─── Scale Group ──────────────────────────────────────────────────
// A single type group in the scale panel accordion.
// DS-1 §4.2: Header with type label + count + rollup.
// DS-1 §4.3: Click header → expand/collapse (local, no navigation).
// Click Narrative: When onChevronToggle is provided, the chevron
// toggles expand/collapse independently of the header click
// (which triggers group selection instead).
// DS-2 §3: Pips for rollup action count indicators.

import type { ConnectedGroup, RenderMode } from "@/types/navigation";
import { ScaleInstance } from "./ScaleInstance";

interface ScaleGroupProps {
  group: ConnectedGroup;
  /** Render mode from type config — used for display variations. */
  renderMode?: RenderMode;
  expanded: boolean;
  /** Header click handler (either toggle or group selection). */
  onToggle: () => void;
  /** Separate chevron toggle (when header click selects instead of toggling). */
  onChevronToggle?: () => void;
  /** SELECT callback — shows item detail without navigating. */
  onSelect: (itemId: string) => void;
  /** Currently selected item ID (for highlight). */
  selectedItemId?: string | null;
  /** Whether this group is the currently selected category. */
  selected?: boolean;
  /** Whether comparison mode is active (drives pip filled state). */
  comparisonActive?: boolean;
}

export function ScaleGroup({
  group,
  renderMode,
  expanded,
  onToggle,
  onChevronToggle,
  onSelect,
  selectedItemId,
  selected = false,
  comparisonActive = false,
}: ScaleGroupProps) {

  const handleChevronClick = onChevronToggle
    ? (e: React.MouseEvent) => {
        e.stopPropagation();
        onChevronToggle();
      }
    : undefined;

  return (
    <div className="border-b border-rule/50 last:border-b-0">
      {/* Group header — clickable to expand/collapse or select category */}
      <button
        type="button"
        onClick={onToggle}
        className={`w-full text-left px-3 py-2 flex items-center gap-2 text-sm transition-colors duration-100 ${
          selected
            ? "bg-board/60 border-l-2 border-l-ink"
            : "hover:bg-board/30"
        }`}
      >
        {/* Expand/collapse chevron */}
        <svg
          onClick={handleChevronClick}
          className={`w-3 h-3 shrink-0 text-trace transition-transform duration-150 ${expanded ? "rotate-90" : ""} ${onChevronToggle ? "cursor-pointer hover:text-graphite" : ""}`}
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

        {/* Type label + count */}
        <span className="font-medium text-ink truncate">
          {group.label}
        </span>
        <span className="text-xs text-trace shrink-0">
          ({group.count})
        </span>
      </button>

      {/* Expanded instance list — CSS grid-rows for smooth animation */}
      <div
        className="grid transition-[grid-template-rows] duration-150 ease-out"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="pb-1">
            {group.items.map((item, index) => (
              <ScaleInstance
                key={item.id}
                item={item}
                ordinal={renderMode === "timeline" ? index + 1 : undefined}
                onSelect={onSelect}
                selected={item.id === selectedItemId}
                comparisonActive={comparisonActive}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
