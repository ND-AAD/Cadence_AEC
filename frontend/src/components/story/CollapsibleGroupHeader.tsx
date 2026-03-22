// ─── Collapsible Group Header ─────────────────────────────────────
// Clickable section header for the project-level data listing.
// Like RowGroupLabel but with a toggle chevron and item count.
// Reuses the ScaleGroup chevron pattern (rotate-90 on expand).

interface CollapsibleGroupHeaderProps {
  label: string;
  count: number;
  expanded: boolean;
  onToggle: () => void;
}

export function CollapsibleGroupHeader({
  label,
  count,
  expanded,
  onToggle,
}: CollapsibleGroupHeaderProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="w-full text-left px-4 py-1.5 flex items-center gap-2 bg-vellum/50 hover:bg-vellum transition-colors duration-100 cursor-pointer"
    >
      <svg
        className={`w-3 h-3 shrink-0 text-trace transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
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
      <span className="text-xs font-mono text-trace uppercase tracking-wide">
        {label}
      </span>
      <span className="text-xs text-trace">
        ({count})
      </span>
    </button>
  );
}
