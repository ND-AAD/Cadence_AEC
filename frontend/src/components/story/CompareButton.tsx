// ─── Compare Button ──────────────────────────────────────────
// Standalone toggle for comparison mode.
// Per DS-2 Addendum v3 §2.2.
//
// Inactive: text "Compare", border, transparent bg
// Active: text "Compare ×", overlay-blue color, overlay-wash bg
// Hidden in Quiet mode
//
// DTC-2: Click to toggle comparison (calls onToggle, which typically
// opens milestone picker or deactivates comparison in parent).

interface CompareButtonProps {
  isActive: boolean;
  onToggle: () => void;
  visible?: boolean; // Hidden when false (Quiet mode)
}

export function CompareButton({
  isActive,
  onToggle,
  visible = true,
}: CompareButtonProps) {
  if (!visible) return null;

  const baseStyle: React.CSSProperties = {
    fontFamily: "var(--font-mono, ui-monospace, monospace)",
    fontSize: "10px",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    padding: "4px 12px",
    border: "1px solid",
    borderRadius: "3px",
    cursor: "pointer",
    whiteSpace: "nowrap",
    background: "transparent",
    transition: "color 0.15s, border-color 0.15s, background 0.15s",
  };

  const inactiveStyle: React.CSSProperties = {
    color: "var(--graphite, rgba(28, 27, 24, 0.60))",
    borderColor: "var(--rule, rgba(28, 27, 24, 0.12))",
  };

  const activeStyle: React.CSSProperties = {
    color: "var(--overlay, #0066CC)",
    borderColor: "var(--overlay-border, rgba(0, 102, 204, 0.20))",
    background: "var(--overlay-wash, rgba(0, 102, 204, 0.08))",
  };

  const hoverStyle: React.CSSProperties = isActive
    ? {}
    : {
        color: "var(--ink, #1C1B18)",
        borderColor: "var(--rule-emphasis, rgba(28, 27, 24, 0.20))",
      };

  return (
    <button
      type="button"
      onClick={onToggle}
      style={{
        ...baseStyle,
        ...(isActive ? activeStyle : inactiveStyle),
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          (e.currentTarget as HTMLButtonElement).style.color =
            hoverStyle.color as string;
          (e.currentTarget as HTMLButtonElement).style.borderColor =
            hoverStyle.borderColor as string;
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          (e.currentTarget as HTMLButtonElement).style.color =
            inactiveStyle.color as string;
          (e.currentTarget as HTMLButtonElement).style.borderColor =
            inactiveStyle.borderColor as string;
        }
      }}
      title={isActive ? "Exit comparison" : "Compare two milestones"}
    >
      {isActive ? "Compare ×" : "Compare"}
    </button>
  );
}
