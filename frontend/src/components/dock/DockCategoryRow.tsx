// ─── Dock Category Row ────────────────────────────────────────────
// Level 1 of the exec summary dock tree.
// system.md: text-sm font-semibold tracking-tight in category ink color.
// border-l-2 in category accent. Count badge in category wash+ink.
// Chevron for expand/collapse. Smooth CSS grid-rows animation.

import { useState, useCallback, type ReactNode } from "react";
import type { DockCategory } from "@/types/dashboard";
import { Pip } from "@/components/story/Pip";

// Map category color classes to pip colors.
const PIP_COLOR_MAP: Record<DockCategory["colorClass"], "redline" | "pencil" | "overlay"> = {
  redline: "redline",
  pencil: "pencil",
  overlay: "overlay",
  stamp: "pencil",  // resolved uses pencil color family
  trace: "pencil",  // notes placeholder
};

// ─── Color class map (Tailwind can't compute dynamic classes) ────

const COLOR_MAP: Record<
  DockCategory["colorClass"],
  {
    border: string;
    text: string;
    badgeBg: string;
    badgeText: string;
  }
> = {
  redline: {
    border: "border-l-redline",
    text: "text-redline-ink",
    badgeBg: "bg-redline-wash",
    badgeText: "text-redline-ink",
  },
  pencil: {
    border: "border-l-pencil",
    text: "text-pencil-ink",
    badgeBg: "bg-pencil-wash",
    badgeText: "text-pencil-ink",
  },
  overlay: {
    border: "border-l-overlay",
    text: "text-overlay",
    badgeBg: "bg-overlay-wash",
    badgeText: "text-overlay",
  },
  stamp: {
    border: "border-l-stamp",
    text: "text-stamp-ink",
    badgeBg: "bg-stamp-wash",
    badgeText: "text-stamp-ink",
  },
  trace: {
    border: "border-l-transparent",
    text: "text-graphite",
    badgeBg: "bg-board",
    badgeText: "text-trace",
  },
};

// ─── Chevron SVG ─────────────────────────────────────────────────

function Chevron({ expanded, className }: { expanded: boolean; className?: string }) {
  return (
    <svg
      className={`w-3 h-3 transition-transform duration-150 ${expanded ? "rotate-90" : ""} ${className ?? ""}`}
      viewBox="0 0 12 12"
      fill="none"
    >
      <path
        d="M4.5 2.5L8 6l-3.5 3.5"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ─── Component ───────────────────────────────────────────────────

interface DockCategoryRowProps {
  category: DockCategory;
  children?: ReactNode;
  /** Whether this category is expanded (controlled from parent). */
  isExpanded?: boolean;
}

export function DockCategoryRow({
  category,
  children,
  isExpanded,
}: DockCategoryRowProps) {
  const [localExpanded, setLocalExpanded] = useState(category.defaultExpanded);
  // isExpanded acts as a "force open" signal (e.g., when a child is selected
  // via workflow perspective). Manual toggle always works independently.
  const expanded = localExpanded || (isExpanded ?? false);
  const toggle = useCallback(() => {
    setLocalExpanded((prev) => !prev);
  }, []);

  const colors = COLOR_MAP[category.colorClass];
  const hasChildren = category.groups.length > 0;

  return (
    <div className={`border-l-2 ${colors.border} border-b border-rule/50 last:border-b-0`}>
      {/* Category header — clickable */}
      <button
        onClick={hasChildren ? toggle : undefined}
        className={`w-full flex items-center gap-2 px-3 py-2 text-sm font-medium ${colors.text} ${hasChildren ? "cursor-pointer hover:bg-board/40" : "cursor-default"} transition-colors duration-100`}
        type="button"
      >
        {/* Chevron (only if expandable) */}
        {hasChildren ? (
          <Chevron expanded={expanded} className={colors.text} />
        ) : (
          <span className="w-3" />
        )}

        {/* Label */}
        <span className="flex-1 text-left">{category.label}</span>

        {/* Count — matches dashboard "(N)" format, pip adds workflow signal */}
        {category.count > 0 && (
          <span className="inline-flex items-center gap-1.5 shrink-0">
            <span className="text-xs text-trace">
              ({category.count})
            </span>
            <Pip filled color={PIP_COLOR_MAP[category.colorClass]} tooltip={`${category.count} ${category.label.toLowerCase()}`} />
          </span>
        )}
      </button>

      {/* Expandable children (CSS grid-rows for smooth animation) */}
      {hasChildren && (
        <div
          className="grid transition-[grid-template-rows] duration-150 ease-out"
          style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
        >
          <div className="overflow-hidden"><div className="pb-1">{children}</div></div>
        </div>
      )}
    </div>
  );
}
