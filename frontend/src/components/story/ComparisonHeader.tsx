// ─── Comparison Header ────────────────────────────────────────────
// Column labels rendered above property rows when comparison is active.
// Aligns to the PropertyRow comparison grid: 120px | 1fr | 1fr | 28px.
//
// DS-2 §2.1: Environmental transformation includes column labeling
// so the user always knows which milestone maps to which column.

interface ComparisonHeaderProps {
  /** Label for the "from" (older) context column. */
  fromLabel: string;
  /** Label for the "to" (newer) context column. */
  toLabel: string;
}

export function ComparisonHeader({ fromLabel, toLabel }: ComparisonHeaderProps) {
  return (
    <div className="grid grid-cols-[120px_1fr_1fr_28px] gap-x-3 items-center px-4 h-8 border-b border-overlay-border/30">
      {/* Label column spacer */}
      <div />
      {/* From context */}
      <span className="text-xs font-mono uppercase text-overlay-border truncate">
        {fromLabel}
      </span>
      {/* To context */}
      <span className="text-xs font-mono uppercase text-overlay-border truncate">
        {toLabel}
      </span>
      {/* Indicator lane spacer */}
      <div />
    </div>
  );
}
