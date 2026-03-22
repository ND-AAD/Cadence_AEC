// ─── Kernel Button ────────────────────────────────────────────────
// Persistent toggle button for collapsible side panels.
// Always visible — even when the panel is collapsed.
// DS-1 §2.3: "Always visible even when panel is collapsed."

interface KernelButtonProps {
  /** Which direction the panel opens toward. */
  direction: "left" | "right";
  /** Whether the panel is currently open. */
  isOpen: boolean;
  /** Toggle callback. */
  onToggle: () => void;
  /** Accessible label. */
  label: string;
  /** Optional count indicator (e.g., note count). */
  count?: number;
}

export function KernelButton({
  direction,
  isOpen,
  onToggle,
  label,
  count,
}: KernelButtonProps) {
  // Chevron indicates what clicking will DO, not the current state.
  // Left panel: closed → ">" (click to expand right), open → "<" (click to collapse left).
  // Right panel: closed → "<" (click to expand left), open → ">" (click to collapse right).
  const showLeftChevron =
    (direction === "left" && isOpen) || (direction === "right" && !isOpen);

  return (
    <button
      onClick={onToggle}
      aria-label={label}
      className="w-12 h-12 flex items-center justify-center text-graphite hover:text-ink hover:bg-board/60 transition-colors duration-150 shrink-0"
    >
      <div className="relative">
        <svg
          className="w-4 h-4"
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d={showLeftChevron ? "M10 3L5 8l5 5" : "M6 3l5 5-5 5"}
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        {count !== undefined && count > 0 && (
          <span className="absolute -top-1.5 -right-2 text-[9px] font-medium text-graphite bg-board rounded-full w-4 h-4 flex items-center justify-center">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </div>
    </button>
  );
}
