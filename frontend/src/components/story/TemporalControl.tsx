// ─── Temporal Control ──────────────────────────────────────────
// Unified temporal surface: view mode selector (single/compare),
// value mode selector (submitted/cumulative), and Current toggle.
//
// Implements the tray model from DS-2 Addendum §3.2.
// CSS matches the v16 reference mockup (ds2-temporal-controls.html).
//
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
  viewMode: ViewMode;
  valueMode: ValueMode;
  isCurrent: boolean;
  onViewModeChange: (mode: ViewMode) => void;
  onValueModeChange: (mode: ValueMode) => void;
  onCurrentToggle: () => void;
  visible?: boolean;
}

// ── CSS custom properties matching the v16 mockup ──
const TC = {
  tray: "#D4D2CE",
  trayRadius: "3px",
  btnRadius: "2.5px",
  pad: "2px",
  gap: "3px",
  btnW: "72px",
  btnH: "22px",
  innerGap: "7px",
} as const;

// Shared styles extracted as objects to match the mockup exactly.
const trayStyle: React.CSSProperties = {
  background: TC.tray,
  borderRadius: TC.trayRadius,
  padding: TC.pad,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};

const btnStyle: React.CSSProperties = {
  fontFamily: "var(--font-mono, ui-monospace, monospace)",
  fontSize: "9px",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  lineHeight: TC.btnH,
  height: TC.btnH,
  width: TC.btnW,
  textAlign: "center",
  padding: 0,
  border: "none",
  borderRadius: TC.btnRadius,
  cursor: "pointer",
  userSelect: "none",
  whiteSpace: "nowrap",
  transition: "background 0.15s, color 0.15s, box-shadow 0.15s",
};

const btnActiveStyle: React.CSSProperties = {
  background: "#FFFFFF",
  color: "var(--ink, #1C1B18)",
  fontWeight: 600,
  boxShadow:
    "0 0.5px 1px rgba(28, 27, 24, 0.06), inset 0 0 0 0.5px rgba(28, 27, 24, 0.08)",
};

const btnInactiveStyle: React.CSSProperties = {
  background: "transparent",
  color: "rgba(28, 27, 24, 0.40)",
  fontWeight: 400,
  boxShadow: "none",
};

export function TemporalControl({
  viewMode,
  valueMode,
  isCurrent,
  onViewModeChange,
  onValueModeChange,
  onCurrentToggle,
  visible = true,
}: TemporalControlProps) {
  if (!visible) return null;

  const on = (active: boolean) => ({
    ...btnStyle,
    ...(active && !isCurrent ? btnActiveStyle : btnInactiveStyle),
  });

  const dimmed: React.CSSProperties = isCurrent
    ? { opacity: 0.3, pointerEvents: "none" }
    : {};

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "auto auto auto",
        gridTemplateRows: "auto auto",
        gap: TC.gap,
      }}
    >
      {/* Single tray (col 1, row 1) */}
      <div style={{ ...trayStyle, gridColumn: 1, gridRow: 1, ...dimmed }}>
        <button
          type="button"
          onClick={() => onViewModeChange("single")}
          disabled={isCurrent}
          style={on(viewMode === "single")}
          title="Single milestone view"
        >
          Single
        </button>
      </div>

      {/* Compare tray (col 2, row 1) */}
      <div style={{ ...trayStyle, gridColumn: 2, gridRow: 1, ...dimmed }}>
        <button
          type="button"
          onClick={() => onViewModeChange("compare")}
          disabled={isCurrent}
          style={on(viewMode === "compare")}
          title="Compare two milestones"
        >
          Compare
        </button>
      </div>

      {/* Value tray (col 1–2, row 2) — segmented pair */}
      <div
        style={{
          ...trayStyle,
          gridColumn: "1 / 3",
          gridRow: 2,
          gap: TC.innerGap,
          ...dimmed,
        }}
      >
        <button
          type="button"
          onClick={() => onValueModeChange("submitted")}
          disabled={isCurrent}
          style={on(valueMode === "submitted")}
          title="Show submitted values only"
        >
          Submitted
        </button>
        <button
          type="button"
          onClick={() => onValueModeChange("cumulative")}
          disabled={isCurrent}
          style={on(valueMode === "cumulative")}
          title="Show cumulative (carried-forward) values"
        >
          Cumulative
        </button>
      </div>

      {/* Current tray (col 3, row 1–2) */}
      <div style={{ ...trayStyle, gridColumn: 3, gridRow: "1 / 3" }}>
        <button
          type="button"
          onClick={onCurrentToggle}
          style={{
            ...btnStyle,
            ...(isCurrent ? btnActiveStyle : btnInactiveStyle),
            width: TC.btnW,
            height: "100%",
            lineHeight: "1",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          title="View latest values across all milestones"
        >
          Current
        </button>
      </div>
    </div>
  );
}
