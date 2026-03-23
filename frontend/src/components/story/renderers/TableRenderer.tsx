// ─── Table Renderer ───────────────────────────────────────────────
// Render mode "table": tabular grid with property columns.
// DS-1 §5.2: Types with many structured properties (doors, schedules,
// changes, conflicts, directives). Columns derived from TypeConfig
// properties definition.
// DS-2 §3: Pips for action count indicators.

import type { RendererProps } from "./ListRenderer";
import { RowGroupLabel } from "../RowGroupLabel";
import { IndicatorLane } from "../IndicatorLane";
import { buildPips, presentCategories } from "@/utils/buildPips";
import { itemDisplayName } from "@/utils/displayName";

export function TableRenderer({
  group,
  typeConfig,
  breadcrumbIds,
  onNavigate,
  comparisonActive = false,
}: RendererProps) {
  // Get column definitions from type config. If no type config, show identifier only.
  const columns = typeConfig?.properties?.slice(0, 5) ?? [];

  return (
    <div>
      <RowGroupLabel label={group.label} />
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          {/* Column headers */}
          <thead>
            <tr className="border-b border-rule">
              <th className="text-left px-4 py-1.5 text-trace font-mono uppercase tracking-wide font-normal">
                Identifier
              </th>
              {columns.map((col) => (
                <th
                  key={col.name}
                  className="text-left px-3 py-1.5 text-trace font-mono uppercase tracking-wide font-normal"
                >
                  {col.label}
                </th>
              ))}
              <th className="text-right px-4 py-1.5 text-trace font-mono uppercase tracking-wide font-normal w-[28px]">
                <span className="sr-only">Status</span>
              </th>
            </tr>
          </thead>

          {/* Data rows */}
          <tbody className="divide-y divide-rule/50">
            {group.items.map((item) => {
              const name = itemDisplayName(item.identifier, item.item_type);
              const inPath = breadcrumbIds.has(item.id);
              const pips = buildPips(item.action_counts, presentCategories(comparisonActive));

              return (
                <tr
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className="cursor-pointer hover:bg-board/40 transition-colors duration-100 group"
                >
                  <td
                    className={`px-4 py-2 font-mono ${inPath ? "text-trace" : "text-ink"}`}
                  >
                    {name}
                  </td>

                  {/* Property columns — placeholder: we don't have per-item
                      property data in ItemSummary. Columns render as "—" for
                      now. Full property data comes when the story panel fetches
                      the item detail on click. */}
                  {columns.map((col) => (
                    <td
                      key={col.name}
                      className="px-3 py-2 font-mono text-trace"
                    >
                      —
                    </td>
                  ))}

                  {/* Indicator lane */}
                  <td className="px-2 py-2 text-right">
                    {pips.length > 0 ? (
                      <IndicatorLane pips={pips} />
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
