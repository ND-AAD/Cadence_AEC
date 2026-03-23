// ─── Card Renderer ────────────────────────────────────────────────
// Render mode "cards": visual cards with summary info.
// DS-1 §5.2: Types that represent containers or entities
// (projects, rooms, portfolios, firms). Responsive 2-3 column grid.
// DS-2 §3: Pips for action count indicators.

import type { RendererProps } from "./ListRenderer";
import { RowGroupLabel } from "../RowGroupLabel";
import { IndicatorLane } from "../IndicatorLane";
import { buildPips, presentCategories } from "@/utils/buildPips";
import { itemDisplayName } from "@/utils/displayName";

export function CardRenderer({
  group,
  breadcrumbIds,
  onNavigate,
  comparisonActive = false,
}: RendererProps) {
  return (
    <div>
      <RowGroupLabel label={group.label} />
      <div className="px-4 py-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {group.items.map((item) => {
          const name = itemDisplayName(item.identifier, item.item_type);
          const inPath = breadcrumbIds.has(item.id);
          const pips = buildPips(item.action_counts, presentCategories(comparisonActive));

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              className={`text-left p-3 rounded border transition-colors duration-100 cursor-pointer group ${
                inPath
                  ? "bg-board/30 border-rule-emphasis text-trace"
                  : "bg-vellum border-rule hover:bg-board/40 hover:border-rule-emphasis"
              }`}
            >
              {/* Item name */}
              <span
                className={`block font-mono text-sm truncate ${
                  inPath ? "text-trace" : "text-ink font-medium"
                }`}
              >
                {name}
              </span>

              {/* Indicator pips */}
              <span className="mt-1.5 flex items-center gap-1.5">
                {pips.length > 0 ? (
                  <IndicatorLane pips={pips} />
                ) : (
                  <span className="text-xs text-trace">&nbsp;</span>
                )}
              </span>

              {/* Forward arrow on hover */}
              <svg
                className="w-3 h-3 ml-auto mt-1.5 text-trace opacity-0 group-hover:opacity-100 transition-opacity duration-150"
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
            </button>
          );
        })}
      </div>
    </div>
  );
}
