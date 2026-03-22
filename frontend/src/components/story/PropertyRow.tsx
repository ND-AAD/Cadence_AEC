// ─── Property Row ─────────────────────────────────────────────────
// The core display unit for item properties.
// DS-1 §5.4 + DS-2 §2.1 + system.md: type-agnostic, temporal spectrum styling.
//
// Single mode grid:     120px (label) | 1fr (value) | 28px (indicator lane)
// Comparison mode grid: 120px (label) | 1fr (old)   | 1fr (new) | 28px (indicator)
// Min-height: 34px. Padding: 7px 16px.
//
// Aligned:    value only, no decoration (silence = alignment)
// Changed:    bg-pencil-wash, border-l-2 border-l-pencil
// Conflicted: bg-redline-wash, border-l-2 border-l-redline
// Resolved:   stamp checkmark + "resolved" text
//
// Expansion: row body click toggles expansion panel below the grid row.
// Uses CSS grid-template-rows 0fr/1fr for smooth open/close animation.

import type { ReactNode } from "react";

export type PropertyStatus = "aligned" | "changed" | "conflicted" | "resolved";

export interface ComparisonColumn {
  /** Context label (e.g., milestone name). */
  contextLabel: string;
  /** Rendered value for this column. */
  value: ReactNode;
  /** True = prior context (dimmed). False/undefined = current context (emphasized). */
  isOld?: boolean;
}

interface PropertyRowProps {
  /** Property label (from type config). */
  label: string;
  /** Temporal spectrum status. */
  status?: PropertyStatus;
  /** Formatted value or custom content (single-column mode). */
  children: ReactNode;
  /** Content for the indicator lane (pips, cairns). */
  indicators?: ReactNode;
  /** Click handler for row body (expand in-place — DS-2 §4). */
  onRowClick?: () => void;
  /** When present, render two value columns instead of one. */
  comparisonColumns?: [ComparisonColumn, ComparisonColumn];
  /** Whether the expansion panel is open. */
  expanded?: boolean;
  /** Toggle expansion (lifted to parent). */
  onToggle?: () => void;
  /** Content rendered below the row when expanded. */
  expansionContent?: ReactNode;
}

const statusStyles: Record<PropertyStatus, string> = {
  aligned: "",
  changed: "bg-pencil-wash border-l-2 border-l-pencil",
  conflicted: "bg-redline-wash border-l-2 border-l-redline",
  resolved: "",
};

function ResolvedValue({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <svg className="w-3.5 h-3.5 text-stamp shrink-0" viewBox="0 0 14 14" fill="none">
        <path d="M3 7l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-stamp-ink text-xs">resolved</span>
      <span className="font-mono text-base-size">{children}</span>
    </div>
  );
}

export function PropertyRow({
  label,
  status = "aligned",
  children,
  indicators,
  onRowClick,
  comparisonColumns,
  expanded = false,
  onToggle,
  expansionContent,
}: PropertyRowProps) {
  const isComparison = !!comparisonColumns;
  const isClickable = !!(onRowClick || onToggle);
  const handleClick = onRowClick ?? onToggle;

  const gridCols = isComparison
    ? "grid-cols-[120px_1fr_1fr_28px]"
    : "grid-cols-[120px_1fr_28px]";

  return (
    <div>
      {/* ── Main row ── */}
      <div
        className={`grid ${gridCols} gap-x-3 items-start px-4 min-h-[34px] py-[7px] text-sm ${statusStyles[status]} ${isClickable ? "cursor-pointer hover:bg-board/20" : ""}`}
        onClick={handleClick}
        role={isClickable ? "button" : undefined}
        tabIndex={isClickable ? 0 : undefined}
        onKeyDown={
          isClickable
            ? (e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleClick?.();
                }
              }
            : undefined
        }
        aria-expanded={expansionContent != null ? expanded : undefined}
      >
        {/* Label column — 120px */}
        <span className="text-graphite text-xs leading-[20px] truncate">
          {label}
        </span>

        {isComparison && comparisonColumns ? (
          <>
            {comparisonColumns.map((col, i) => {
              // Changed rows: old value in trace, new in pencil-ink.
              // Unchanged rows (aligned): both in neutral ink.
              const colStyle = status === "changed"
                ? (col.isOld ? "text-trace" : "text-pencil-ink font-medium")
                : "";
              return (
                <div key={i} className={`min-w-0 ${colStyle}`}>
                  {status === "resolved" ? (
                    <ResolvedValue>{col.value}</ResolvedValue>
                  ) : (
                    col.value
                  )}
                </div>
              );
            })}
          </>
        ) : (
          /* Single value column — 1fr */
          <div className="min-w-0">
            {status === "resolved" ? (
              <ResolvedValue>{children}</ResolvedValue>
            ) : (
              children
            )}
          </div>
        )}

        {/* Indicator lane — 28px */}
        <div className="flex flex-row-reverse items-center justify-start h-full">
          {indicators}
        </div>
      </div>

      {/* ── Expansion panel ── */}
      {expansionContent != null && (
        <div
          className="grid transition-[grid-template-rows] duration-200 ease-in-out"
          style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
        >
          <div className="overflow-hidden">
            <div className="px-4 pb-3 pt-1">{expansionContent}</div>
          </div>
        </div>
      )}
    </div>
  );
}
