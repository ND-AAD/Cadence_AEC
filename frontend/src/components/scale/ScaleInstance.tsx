// ─── Scale Instance ───────────────────────────────────────────────
// A single clickable item row within a scale panel accordion group.
// DS-1 §4.5: identifier + compact rollup + note indicators.
// Click triggers SELECT (show detail in main area, no navigation).
// Click Narrative §3.2: "Left panel click = SELECT, not a zoom."
// DS-2 §3: Pips for action count indicators.

import type { ItemSummary } from "@/types/navigation";
import { itemDisplayName } from "@/utils/displayName";

interface ScaleInstanceProps {
  item: ItemSummary;
  /** Ordinal number for timeline-mode types (1, 2, 3...). */
  ordinal?: number;
  /** SELECT callback — shows item detail in main area without navigating. */
  onSelect: (itemId: string) => void;
  /** Whether this item is currently selected (highlighted). */
  selected?: boolean;
  /** Whether comparison mode is active (drives pip filled state). */
  comparisonActive?: boolean;
}

export function ScaleInstance({ item, ordinal, onSelect, selected = false }: ScaleInstanceProps) {
  const name = itemDisplayName(item.identifier, item.item_type);

  return (
    <button
      type="button"
      onClick={() => onSelect(item.id)}
      className={`w-full text-left px-3 py-1.5 flex items-center gap-2 text-sm group cursor-pointer transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-[-2px] ${
        selected
          ? "bg-board/60 border-l-2 border-l-ink"
          : "hover:bg-board/40"
      }`}
    >
      {/* Ordinal marker for timeline-mode types */}
      {ordinal !== undefined && (
        <span className="text-xs font-mono text-trace w-4 text-right shrink-0">
          {ordinal}
        </span>
      )}

      {/* Item identifier */}
      <span className="font-mono text-ink truncate flex-1 min-w-0">
        {name}
      </span>

      {/* Forward chevron on hover */}
      <svg
        className="w-3 h-3 shrink-0 text-trace opacity-0 group-hover:opacity-100 transition-opacity duration-100"
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
  );
}
