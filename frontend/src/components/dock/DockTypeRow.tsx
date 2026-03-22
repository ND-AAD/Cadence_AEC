// ─── Dock Type Row ────────────────────────────────────────────────
// Level 2 of the exec summary dock tree.
// system.md: text-xs font-medium text-ink. Indented under category.
// Pip + count in category color. Clickable for navigation (future).

import type { DockTypeGroup, DockCategory } from "@/types/dashboard";
import { Pip, type PipColor } from "@/components/story/Pip";

// Map category color to pip color.
const PIP_COLOR: Record<DockCategory["colorClass"], PipColor> = {
  redline: "redline",
  pencil: "pencil",
  overlay: "overlay",
  stamp: "pencil",
  trace: "pencil",
};

interface DockTypeRowProps {
  group: DockTypeGroup;
  colorClass: DockCategory["colorClass"];
  /** Whether this row is currently selected. */
  isSelected?: boolean;
  /** Click handler for workflow perspective selection. */
  onClick?: () => void;
}

export function DockTypeRow({
  group,
  colorClass,
  isSelected = false,
  onClick,
}: DockTypeRowProps) {
  // Map colorClass to background color for selected state
  const selectedBgColor: Record<DockCategory["colorClass"], string> = {
    redline: "bg-redline-wash/40",
    pencil: "bg-pencil-wash/40",
    overlay: "bg-overlay-wash/40",
    stamp: "bg-stamp-wash/40",
    trace: "bg-board/20",
  };

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-1.5 flex items-center gap-2 text-sm transition-colors duration-100 ${
        isSelected ? `${selectedBgColor[colorClass]} border-l-2 border-l-current` : ""
      } ${onClick ? "cursor-pointer hover:bg-board/40" : "cursor-default"}`}
      type="button"
    >
      {/* Label — matches ScaleInstance: font-mono text-ink */}
      <span className="font-mono text-ink truncate flex-1 min-w-0">{group.label}</span>

      {/* Pip + count */}
      <span className="inline-flex items-center gap-1.5 shrink-0">
        <span className={`text-xs text-trace`}>({group.count})</span>
        <Pip filled color={PIP_COLOR[colorClass]} />
      </span>
    </button>
  );
}
