// ─── Temporal Control ──────────────────────────────────────────
// Unified temporal surface: view mode selector (single/compare),
// value mode selector (submitted/cumulative), and Current toggle.
//
// Implements the tray model from DS-2 Addendum §3.2.
// CSS Grid layout with four tray pieces as direct grid children:
//
//   ┌──────────┐ ┌──────────┐ ┌─────────┐
//   │  Single  │ │ Compare  │ │         │
//   └──────────┘ └──────────┘ │ Current │
//   ┌──────────┬──────────┐   │         │
//   │Submitted │Cumulative│   └─────────┘
//   └──────────┴──────────┘
//
// Grid gap (3px) between all tray pieces ensures consistent spacing.
// Value tray spans cols 1-2; its inner gap (7px) = pad + gap + pad
// so Single centers over Submitted and Compare over Cumulative.

import type { ViewMode, ValueMode } from "@/context/ComparisonContext";

interface TemporalControlProps {
  /** Current view mode. */
  viewMode: ViewMode;
  /** Current value mode. */
  valueMode: ValueMode;
  /** True if in Current mode. */
  isCurrent: boolean;
  /** Callback when view mode changes. */
  onViewModeChange: (mode: ViewMode) => void;
  /** Callback when value mode changes. */
  onValueModeChange: (mode: ValueMode) => void;
  /** Callback when Current mode is toggled. */
  onCurrentToggle: () => void;
  /** Whether the control is visible. */
  visible?: boolean;
}

export function TemporalControl({
  viewMode,
  valueMode,
  isCurrent,
  onViewModeChange,
  onValueModeChange,
  onCurrentToggle,
  visible = true,
}: TemporalControlProps) {
  if (!visible) {
    return null;
  }

  // Shared tray styling
  const tray = "bg-[#D4D2CE] rounded-[3px] p-[2px]";

  // Button styling
  const btnBase = [
    "w-[72px] h-[22px] rounded-[2.5px]",
    "font-mono text-[9px] uppercase tracking-[0.04em]",
    "transition-all duration-100",
    "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ink",
  ].join(" ");

  const btnActive = [
    "bg-white text-ink font-semibold",
    "shadow-[inset_0_0_0_0.5px_rgba(28,27,24,0.08),0_0.5px_1px_rgba(28,27,24,0.06)]",
  ].join(" ");

  const btnInactive = [
    "bg-transparent text-[rgba(28,27,24,0.4)]",
    "hover:bg-[rgba(255,255,255,0.2)] hover:text-[rgba(28,27,24,0.65)]",
  ].join(" ");

  // Dimming for left-column trays when Current is active (§3.2)
  const leftDim = isCurrent ? "opacity-30 pointer-events-none" : "";

  const btn = (active: boolean) =>
    `${btnBase} ${active && !isCurrent ? btnActive : btnInactive}`;

  return (
    <div
      className="grid gap-[3px]"
      style={{
        gridTemplateColumns: "auto auto auto",
        gridTemplateRows: "auto auto",
      }}
    >
      {/* Single tray (col 1, row 1) */}
      <div
        className={`${tray} ${leftDim}`}
        style={{ gridColumn: 1, gridRow: 1 }}
      >
        <button
          type="button"
          onClick={() => onViewModeChange("single")}
          disabled={isCurrent}
          className={btn(viewMode === "single")}
          title="Single milestone view"
        >
          Single
        </button>
      </div>

      {/* Compare tray (col 2, row 1) */}
      <div
        className={`${tray} ${leftDim}`}
        style={{ gridColumn: 2, gridRow: 1 }}
      >
        <button
          type="button"
          onClick={() => onViewModeChange("compare")}
          disabled={isCurrent}
          className={btn(viewMode === "compare")}
          title="Compare two milestones"
        >
          Compare
        </button>
      </div>

      {/* Value tray (col 1–2, row 2) — segmented pair */}
      <div
        className={`${tray} flex gap-[7px] ${leftDim}`}
        style={{ gridColumn: "1 / 3", gridRow: 2 }}
      >
        <button
          type="button"
          onClick={() => onValueModeChange("submitted")}
          disabled={isCurrent}
          className={btn(valueMode === "submitted")}
          title="Show submitted values only"
        >
          Submitted
        </button>
        <button
          type="button"
          onClick={() => onValueModeChange("cumulative")}
          disabled={isCurrent}
          className={btn(valueMode === "cumulative")}
          title="Show cumulative (carried-forward) values"
        >
          Cumulative
        </button>
      </div>

      {/* Current tray (col 3, row 1–2) */}
      <div
        className={`${tray} flex items-stretch`}
        style={{ gridColumn: 3, gridRow: "1 / 3" }}
      >
        <button
          type="button"
          onClick={onCurrentToggle}
          className={btn(isCurrent)}
          style={{ height: "100%" }}
          title="View latest values across all milestones"
        >
          Current
        </button>
      </div>
    </div>
  );
}
