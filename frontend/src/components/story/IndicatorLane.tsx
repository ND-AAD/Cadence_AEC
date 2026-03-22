// ─── Indicator Lane ───────────────────────────────────────────────
// Container for pips and cairns in the 28px indicator lane column.
// DS-2 §3: flex-row-reverse, first child rightmost (highest priority).
//
// Ordering (right to left):
//   1. Cairn (if present — always position 1)
//   2. Present pips (exact context match):
//      Directive → Conflict → Change
//   3. Adjacent pips (nearby, not aligned):
//      Directive → Conflict → Change

import { Pip, type PipColor } from "./Pip";
import { Cairn } from "./Cairn";

export type { PipColor };

export interface PipData {
  /** Filled (present) or hollow (adjacent). */
  filled: boolean;
  /** Temporal spectrum color. */
  color: PipColor;
  /** Tooltip for hover. */
  tooltip?: string;
  /** Key for React list rendering. */
  key: string;
}

export interface CairnData {
  /** Whether the cairn is at the current context (present = filled). */
  present: boolean;
  /** Whether the cairn row is currently expanded (active = inverted). */
  active: boolean;
  /** Tooltip on hover. */
  tooltip?: string;
}

interface IndicatorLaneProps {
  /** Pips to render, ordered by priority (index 0 = rightmost). */
  pips: PipData[];
  /** Cairn data (resolved story marker or note). Renders in position 1 (rightmost). */
  cairn?: CairnData;
  /** Click handler for individual pips (navigates to workflow item). */
  onPipClick?: (index: number) => void;
  /** Click handler for the cairn (expand row in-place). */
  onCairnClick?: () => void;
}

export function IndicatorLane({ pips, cairn, onPipClick, onCairnClick }: IndicatorLaneProps) {
  if (pips.length === 0 && !cairn) return null;

  return (
    <span className="inline-flex flex-row-reverse items-center justify-start gap-0.5 h-full overflow-visible">
      {/* Position 1 (rightmost): Cairn */}
      {cairn && (
        <Cairn
          present={cairn.present}
          active={cairn.active}
          tooltip={cairn.tooltip}
          onClick={onCairnClick}
        />
      )}
      {/* Positions 2+: Pips (present then adjacent) */}
      {pips.map((pip, i) => (
        <Pip
          key={pip.key}
          filled={pip.filled}
          color={pip.color}
          tooltip={pip.tooltip}
          onClick={onPipClick ? () => onPipClick(i) : undefined}
        />
      ))}
    </span>
  );
}
