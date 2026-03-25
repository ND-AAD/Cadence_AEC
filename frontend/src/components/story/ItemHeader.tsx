// ─── Item Header ──────────────────────────────────────────────────
// Item name, context, and type label.
// Per UniversalTemplate prototype: font-mono text-md font-medium.
// T-6: Temporal control (view mode, value mode, Current) replaces
// the comparison toggle button. Includes TemporalControl component.

import type { ItemResponse, TypeConfigEntry } from "@/types/navigation";
import type { ViewMode, ValueMode } from "@/context/ComparisonContext";
import { itemDisplayName } from "@/utils/displayName";
import { TemporalControl } from "./TemporalControl";

interface ItemHeaderProps {
  item: ItemResponse;
  typeConfig?: TypeConfigEntry;
  /** Current view mode (single or compare). */
  viewMode?: ViewMode;
  /** Current value mode (submitted or cumulative). */
  valueMode?: ValueMode;
  /** True if in Current mode. */
  isCurrent?: boolean;
  /** Callback when view mode changes. */
  onViewModeChange?: (mode: ViewMode) => void;
  /** Callback when value mode changes. */
  onValueModeChange?: (mode: ValueMode) => void;
  /** Callback when Current mode is toggled. */
  onCurrentToggle?: () => void;
  /** Whether the temporal control is visible. */
  temporalControlVisible?: boolean;
}

export function ItemHeader({
  item,
  typeConfig,
  viewMode = "single",
  valueMode = "cumulative",
  isCurrent = false,
  onViewModeChange,
  onValueModeChange,
  onCurrentToggle,
  temporalControlVisible = true,
}: ItemHeaderProps) {
  const name = itemDisplayName(item.identifier, item.item_type);
  const typeLabel = typeConfig?.label ?? item.item_type;

  return (
    <div className="px-4 py-3 border-b border-rule flex items-baseline justify-between">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-md font-medium">{name}</span>
        <span className="text-trace">&middot;</span>
        <span className="text-sm text-graphite">{typeLabel}</span>
      </div>

      {/* Temporal control (view mode, value mode, Current) */}
      {onViewModeChange &&
        onValueModeChange &&
        onCurrentToggle && (
          <TemporalControl
            viewMode={viewMode}
            valueMode={valueMode}
            isCurrent={isCurrent}
            onViewModeChange={onViewModeChange}
            onValueModeChange={onValueModeChange}
            onCurrentToggle={onCurrentToggle}
            visible={temporalControlVisible}
          />
        )}
    </div>
  );
}
