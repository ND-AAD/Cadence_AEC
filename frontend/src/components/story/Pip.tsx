// ─── Pip ──────────────────────────────────────────────────────────
// Single indicator dot in the indicator lane.
// DS-2 §6: 7px dot centered in 14px cell.
//
// Filled (solid):  present — exact context match, change visible inline
// Hollow (stroke): adjacent — nearby, not at compared context
//
// Colors follow the temporal spectrum:
//   pencil  (#FA9442) — change
//   redline (#E81A00) — conflict
//   overlay (#002FA7) — directive
//   filed   (#7D7A75) — hold

export type PipColor = "pencil" | "redline" | "overlay" | "filed";

interface PipProps {
  /** Filled (present) or hollow (adjacent). */
  filled: boolean;
  /** Temporal spectrum color. */
  color?: PipColor;
  /** Tooltip text shown on hover. */
  tooltip?: string;
  /** Click handler (navigates to workflow item). */
  onClick?: () => void;
}

// Tailwind classes for each color — filled and hollow variants.
const FILLED_CLASSES: Record<PipColor, string> = {
  pencil: "bg-pencil",
  redline: "bg-redline",
  overlay: "bg-overlay",
  filed: "bg-filed",
};

const HOLLOW_CLASSES: Record<PipColor, string> = {
  pencil: "border-pencil",
  redline: "border-redline",
  overlay: "border-overlay",
  filed: "border-filed",
};

export function Pip({
  filled,
  color = "pencil",
  tooltip,
  onClick,
}: PipProps) {
  const dotClass = filled
    ? `${FILLED_CLASSES[color]} w-[7px] h-[7px] rounded-full`
    : `${HOLLOW_CLASSES[color]} w-[7px] h-[7px] rounded-full border-[1.5px] bg-transparent`;

  const interactiveClass = onClick
    ? "cursor-pointer hover:scale-125 transition-transform duration-100"
    : "";

  return (
    <span
      className={`inline-flex items-center justify-center w-[14px] h-[14px] shrink-0 ${interactiveClass}`}
      title={tooltip}
      onClick={onClick ? (e) => { e.stopPropagation(); onClick(); } : undefined}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                e.stopPropagation();
                onClick();
              }
            }
          : undefined
      }
    >
      <span className={dotClass} />
    </span>
  );
}
