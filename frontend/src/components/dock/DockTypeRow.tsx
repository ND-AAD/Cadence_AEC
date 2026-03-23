// ─── Dock Type Row ────────────────────────────────────────────────
// Level 2 of the exec summary dock tree.
// system.md: text-xs font-medium text-ink. Indented under category.
// Expandable to show level-3 instances. Click instance → navigate.

import { useState } from "react";
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
  /** Navigation handler for instance-level clicks. */
  onNavigate?: (itemId: string) => void;
}

export function DockTypeRow({
  group,
  colorClass,
  isSelected = false,
  onClick,
  onNavigate,
}: DockTypeRowProps) {
  const [expanded, setExpanded] = useState(false);
  const hasInstances = group.instances && group.instances.length > 0;

  const selectedBgColor: Record<DockCategory["colorClass"], string> = {
    redline: "bg-redline-wash/40",
    pencil: "bg-pencil-wash/40",
    overlay: "bg-overlay-wash/40",
    stamp: "bg-stamp-wash/40",
    trace: "bg-board/20",
  };

  const handleClick = () => {
    if (hasInstances) {
      setExpanded((e) => !e);
    }
    onClick?.();
  };

  return (
    <div>
      <button
        onClick={handleClick}
        className={`w-full text-left px-3 py-1.5 flex items-center gap-2 text-sm transition-colors duration-100 ${
          isSelected ? `${selectedBgColor[colorClass]} border-l-2 border-l-current` : ""
        } ${onClick || hasInstances ? "cursor-pointer hover:bg-board/40" : "cursor-default"}`}
        type="button"
      >
        {/* Expand chevron (only when instances exist) */}
        {hasInstances && (
          <svg
            className={`w-2.5 h-2.5 shrink-0 text-trace transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
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
        )}

        {/* Label */}
        <span className="font-mono text-ink truncate flex-1 min-w-0">{group.label}</span>

        {/* Pip + count */}
        <span className="inline-flex items-center gap-1.5 shrink-0">
          <span className="text-xs text-trace">({group.count})</span>
          <Pip filled color={PIP_COLOR[colorClass]} />
        </span>
      </button>

      {/* Level 3: instances */}
      {expanded && hasInstances && (
        <div className="pl-6">
          {group.instances!.map((instance) => (
            <button
              key={instance.id}
              type="button"
              onClick={() => onNavigate?.(instance.id)}
              className="w-full text-left px-3 py-1 text-xs font-mono text-graphite hover:text-ink hover:bg-board/40 transition-colors duration-100 truncate cursor-pointer"
            >
              {instance.identifier}
              {instance.propertyName && (
                <span className="text-trace ml-1">· {instance.propertyName}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
