// ─── Timeline Renderer ────────────────────────────────────────────
// Render mode "timeline": temporally ordered vertical sequence.
// DS-1 §5.2: Types with temporal significance (milestones, phases).
// Vertical timeline with connecting line and clickable nodes.
// DS-2 §3: Pips for action count indicators.

import type { RendererProps } from "./ListRenderer";
import { RowGroupLabel } from "../RowGroupLabel";
import { IndicatorLane } from "../IndicatorLane";
import { buildPips, presentCategories } from "@/utils/buildPips";
import { itemDisplayName } from "@/utils/displayName";

export function TimelineRenderer({
  group,
  breadcrumbIds,
  onNavigate,
  comparisonActive = false,
}: RendererProps) {
  return (
    <div>
      <RowGroupLabel label={group.label} />
      <div className="px-4 py-2">
        {/* Timeline rail */}
        <div className="relative">
          {group.items.map((item, index) => {
            const name = itemDisplayName(item.identifier, item.item_type);
            const inPath = breadcrumbIds.has(item.id);
            const pips = buildPips(item.action_counts, presentCategories(comparisonActive));
            const isLast = index === group.items.length - 1;

            return (
              <div key={item.id} className="flex gap-3 group">
                {/* Timeline column: dot + connecting line */}
                <div className="flex flex-col items-center shrink-0 w-4">
                  {/* Node dot */}
                  <div
                    className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 border ${
                      inPath
                        ? "bg-board border-rule-emphasis"
                        : "bg-vellum border-rule hover:bg-board"
                    }`}
                  />
                  {/* Connecting line */}
                  {!isLast && (
                    <div className="w-px flex-1 bg-rule/60 min-h-[16px]" />
                  )}
                </div>

                {/* Content */}
                <button
                  type="button"
                  onClick={() => onNavigate(item.id)}
                  className="flex-1 min-w-0 text-left pb-3 flex items-center gap-2 cursor-pointer transition-colors duration-100"
                >
                  {/* Ordinal marker */}
                  <span className="text-xs font-mono text-trace shrink-0 w-6 text-right">
                    {index + 1}
                  </span>

                  {/* Name */}
                  <span
                    className={`font-mono text-sm ${
                      inPath ? "text-trace" : "text-ink group-hover:text-ink"
                    }`}
                  >
                    {name}
                  </span>

                  {/* Indicator pips */}
                  {pips.length > 0 && (
                    <span className="shrink-0">
                      <IndicatorLane pips={pips} />
                    </span>
                  )}

                  {/* Forward/back arrow */}
                  <svg
                    className="w-3 h-3 ml-auto shrink-0 text-trace opacity-0 group-hover:opacity-100 transition-opacity duration-150"
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
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
