// ─── Item Header ──────────────────────────────────────────────────
// Item name, context, and type label.
// Per UniversalTemplate prototype: font-mono text-md font-medium.
// DTC-5: Replaced TemporalControl tray with standalone CompareButton.
// Value mode and Quiet controls now live in LayoutFrame and ExecSummaryDock.

import type { ItemResponse, TypeConfigEntry } from "@/types/navigation";
import { itemDisplayName } from "@/utils/displayName";
import { CompareButton } from "./CompareButton";

interface ItemHeaderProps {
  item: ItemResponse;
  typeConfig?: TypeConfigEntry;
  /** True when comparison mode is active. */
  isComparing?: boolean;
  /** Callback to toggle comparison mode. */
  onCompareToggle?: () => void;
  /** Whether the compare button is visible (hidden in Quiet mode). */
  compareVisible?: boolean;
}

export function ItemHeader({
  item,
  typeConfig,
  isComparing = false,
  onCompareToggle,
  compareVisible = true,
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

      {/* Compare toggle (hidden in Quiet mode) */}
      {onCompareToggle && (
        <CompareButton
          isActive={isComparing}
          onToggle={onCompareToggle}
          visible={compareVisible}
        />
      )}
    </div>
  );
}
