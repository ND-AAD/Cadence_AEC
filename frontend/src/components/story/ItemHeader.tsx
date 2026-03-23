// ─── Item Header ──────────────────────────────────────────────────
// Item name, context, and type label.
// Per UniversalTemplate prototype: font-mono text-md font-medium.
// DS-2: Includes comparison toggle button to activate milestone picker.

import type { ItemResponse, TypeConfigEntry } from "@/types/navigation";
import { itemDisplayName } from "@/utils/displayName";

interface ItemHeaderProps {
  item: ItemResponse;
  typeConfig?: TypeConfigEntry;
  /** Whether comparison mode is currently active. */
  comparisonActive?: boolean;
  /** Toggle comparison mode (opens milestone picker or deactivates). */
  onComparisonToggle?: () => void;
}

export function ItemHeader({
  item,
  typeConfig,
  comparisonActive = false,
  onComparisonToggle,
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

      {/* Comparison toggle */}
      {onComparisonToggle && (
        <button
          type="button"
          onClick={onComparisonToggle}
          className={`shrink-0 flex items-center gap-1.5 text-xs px-2 py-1 rounded border transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1 ${
            comparisonActive
              ? "bg-overlay-wash text-overlay border-overlay"
              : "bg-transparent text-graphite border-rule hover:text-ink hover:border-graphite"
          }`}
          title={comparisonActive ? "Deactivate comparison (Ctrl+Shift+C)" : "Compare milestones (Ctrl+Shift+C)"}
        >
          {/* Split-view icon */}
          <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="1" y="2" width="12" height="10" rx="1.5" />
            <line x1="7" y1="2" x2="7" y2="12" />
          </svg>
          <span>{comparisonActive ? "Comparing" : "Compare"}</span>
        </button>
      )}
    </div>
  );
}
