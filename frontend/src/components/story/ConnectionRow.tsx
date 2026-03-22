// ─── Connection Row ───────────────────────────────────────────────
// A navigable link to another item.
// DS-1 §5 + system.md: same row dimensions as PropertyRow.
// Forward items: text-ink, forward arrow on hover.
// In-path items: text-trace, back arrow on hover (snap-back).
// DS-2 §3: Indicator lane with pips for action counts.

import type { ItemSummary } from "@/types/navigation";
import { IndicatorLane } from "./IndicatorLane";
import { buildPips, presentCategories } from "@/utils/buildPips";

interface ConnectionRowProps {
  /** Connection label (e.g., type name). */
  label: string;
  /** The connected item. */
  item: ItemSummary;
  /** True if this item is already in the breadcrumb path (snap-back). */
  inPath: boolean;
  /** Navigation callback. */
  onNavigate: (itemId: string) => void;
  /** Whether comparison mode is active (drives pip filled state). */
  comparisonActive?: boolean;
}

export function ConnectionRow({
  label,
  item,
  inPath,
  onNavigate,
  comparisonActive = false,
}: ConnectionRowProps) {
  const name = item.identifier ?? item.item_type;
  const pips = buildPips(item.action_counts, presentCategories(comparisonActive));

  return (
    <button
      type="button"
      onClick={() => onNavigate(item.id)}
      className="w-full text-left grid grid-cols-[120px_1fr_28px] gap-x-3 items-center px-4 min-h-[34px] py-[7px] text-sm group cursor-pointer transition-colors duration-150 hover:bg-board/40 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-[-2px]"
    >
      <span className="text-graphite text-xs leading-[20px] truncate">{label}</span>
      <div className="min-w-0 flex items-center gap-2">
        <span className={`font-mono ${inPath ? "text-trace" : "text-ink"}`}>
          {name}
        </span>

        {/* Back arrow (in-path) or forward arrow */}
        <svg
          className="w-3.5 h-3.5 ml-auto shrink-0 text-trace opacity-0 group-hover:opacity-100 transition-opacity duration-150"
          viewBox="0 0 14 14"
          fill="none"
        >
          <path
            d={inPath ? "M9 3l-4 4 4 4" : "M5 3l4 4-4 4"}
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      {/* Indicator lane — pips for action counts */}
      {pips.length > 0 ? (
        <IndicatorLane pips={pips} />
      ) : (
        <div />
      )}
    </button>
  );
}
