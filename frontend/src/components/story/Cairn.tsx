// ─── Cairn ───────────────────────────────────────────────────────
// Triangle icon for resolved stories and human-authored notes.
// DS-2 §3.4: 16px container, 10px triangle SVG.
//
// Three states:
//   Present (filled △)  — at your exact context. Solid fill in trace, hover to graphite.
//   Adjacent (hollow △)  — nearby but not at your context. Stroke only, no fill.
//   Active (filled ▽)   — selected/expanded. Triangle inverts (points down).
//
// Cairns are NOT disagreement indicators — they use graphite/trace
// register, not the spectrum color families.

interface CairnProps {
  /** Whether this cairn is at the current context (present = filled). */
  present?: boolean;
  /** Whether the cairn row is currently expanded (active = inverted). */
  active?: boolean;
  /** Tooltip on hover. */
  tooltip?: string;
  /** Click handler (same as row body — expand in-place). */
  onClick?: () => void;
}

export function Cairn({
  present = true,
  active = false,
  tooltip,
  onClick,
}: CairnProps) {
  const isFilled = present;
  const isInverted = active;

  // Triangle path: pointing up (△) or down (▽).
  // 10px triangle centered in 16px container.
  // Vertices at approximately: top=1, bottom-left=9, bottom-right=9
  const upPath = "M5 1 L9 9 L1 9 Z";      // pointing up
  const downPath = "M5 9 L1 1 L9 1 Z";    // pointing down

  const path = isInverted ? downPath : upPath;

  const interactiveClass = onClick
    ? "cursor-pointer hover:text-graphite transition-colors duration-100"
    : "";

  return (
    <span
      className={`inline-flex items-center justify-center w-[16px] h-[16px] shrink-0 text-trace ${interactiveClass}`}
      title={tooltip}
      onClick={
        onClick
          ? (e) => {
              e.stopPropagation();
              onClick();
            }
          : undefined
      }
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
      <svg
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="none"
        className="shrink-0"
      >
        <path
          d={path}
          fill={isFilled ? "currentColor" : "none"}
          stroke={isFilled ? "none" : "currentColor"}
          strokeWidth={isFilled ? "0" : "1.5"}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
