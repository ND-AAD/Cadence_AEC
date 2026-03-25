// ─── Temporal Control ──────────────────────────────────────────
// Unified temporal surface: view mode selector (single/compare),
// value mode selector (submitted/cumulative), and Current toggle.
//
// T-6: Implements the tray model from DS-2 Addendum §3.2.
// Three tray pieces: Single/Compare (top row), Submitted/Cumulative
// (bottom row spanning columns 1-2), Current (right, spanning rows 1-2).
//
// Grid layout:
//   ┌──────────┐ ┌──────────┐ ┌─────────┐
//   │  Single  │ │ Compare  │ │         │
//   └──────────┘ └──────────┘ │ Current │
//   ┌────────────────────────┐│         │
//   │Submitted │ Cumulative  ││         │
//   └────────────────────────┘└─────────┘

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

  // Tray styling: shared background color
  const trayBg = "bg-[#D4D2CE]";
  const trayRounded = "rounded-[3px]";
  const trayPadding = "p-[2px]";

  // Button styling
  const buttonSize = "w-[72px] h-[22px]";
  const buttonRounded = "rounded-[2.5px]";
  const buttonFont = "font-mono text-[9px] uppercase tracking-[0.04em]";
  const buttonBase = `${buttonSize} ${buttonRounded} ${buttonFont} transition-all duration-100 border border-transparent focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ink`;

  // Active button: white, raised, semi-bold
  const buttonActive = `bg-white text-ink font-semibold shadow-[inset_0_0_0_0.5px_rgba(28,27,24,0.08),0_0.5px_1px_rgba(28,27,24,0.06)]`;

  // Inactive button: transparent, trace text, hover state
  const buttonInactive = `bg-transparent text-[rgba(28,27,24,0.4)] hover:bg-[rgba(255,255,255,0.2)] hover:text-[rgba(28,27,24,0.65)]`;

  return (
    <div
      className={`flex gap-[3px] ${
        isCurrent ? "opacity-100" : "opacity-100"
      } transition-opacity duration-100`}
    >
      {/* Left column: view mode (top) and value mode (bottom) */}
      <div className="flex flex-col gap-[3px]">
        {/* Top row: Single and Compare (two separate trays) */}
        <div className="flex gap-[3px]">
          {/* Single tray */}
          <div className={`${trayBg} ${trayRounded} ${trayPadding}`}>
            <button
              type="button"
              onClick={() => onViewModeChange("single")}
              disabled={isCurrent}
              className={`${buttonBase} ${
                viewMode === "single" && !isCurrent
                  ? buttonActive
                  : buttonInactive
              } ${isCurrent ? "opacity-30 cursor-not-allowed" : ""}`}
              title="Single milestone view"
            >
              Single
            </button>
          </div>

          {/* Compare tray */}
          <div className={`${trayBg} ${trayRounded} ${trayPadding}`}>
            <button
              type="button"
              onClick={() => onViewModeChange("compare")}
              disabled={isCurrent}
              className={`${buttonBase} ${
                viewMode === "compare" && !isCurrent
                  ? buttonActive
                  : buttonInactive
              } ${isCurrent ? "opacity-30 cursor-not-allowed" : ""}`}
              title="Compare two milestones"
            >
              Compare
            </button>
          </div>
        </div>

        {/* Bottom row: Submitted and Cumulative (one tray, segmented pair) */}
        <div
          className={`${trayBg} ${trayRounded} ${trayPadding} flex gap-[7px] ${
            isCurrent ? "opacity-30 pointer-events-none" : ""
          }`}
        >
          <button
            type="button"
            onClick={() => onValueModeChange("submitted")}
            disabled={isCurrent}
            className={`${buttonBase} ${
              valueMode === "submitted" && !isCurrent
                ? buttonActive
                : buttonInactive
            }`}
            title="Show submitted values only"
          >
            Submitted
          </button>
          <button
            type="button"
            onClick={() => onValueModeChange("cumulative")}
            disabled={isCurrent}
            className={`${buttonBase} ${
              valueMode === "cumulative" && !isCurrent
                ? buttonActive
                : buttonInactive
            }`}
            title="Show cumulative (carried-forward) values"
          >
            Cumulative
          </button>
        </div>
      </div>

      {/* Right: Current (one tray, spans both rows) */}
      <div
        className={`${trayBg} ${trayRounded} ${trayPadding} flex items-stretch`}
      >
        <button
          type="button"
          onClick={onCurrentToggle}
          className={`${buttonBase} ${
            isCurrent ? buttonActive : buttonInactive
          }`}
          style={{ height: "100%" }}
          title="View latest values across all milestones"
        >
          Current
        </button>
      </div>
    </div>
  );
}
