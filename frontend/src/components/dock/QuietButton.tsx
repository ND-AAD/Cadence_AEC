// ─── Quiet Button ──────────────────────────────────────────
// Toggle for Quiet mode, placed in exec summary panel header.
// Per DS-2 Addendum v3 §2.4.
//
// Inactive: text "Quiet", graphite, transparent bg, rule border
// Active: text "Quiet", ink, board bg, rule-emphasis border
// Full width of header area, centered text
// Subtle difference, matches understated nature of Quiet mode
//
// DTC-4: Quiet replaces "Current" mode conceptually. Backend still
// receives mode=current but the user sees "Quiet."

interface QuietButtonProps {
  isActive: boolean;
  onToggle: () => void;
}

export function QuietButton({ isActive, onToggle }: QuietButtonProps) {
  const baseStyle: React.CSSProperties = {
    width: "100%",
    fontFamily: "var(--font-mono, ui-monospace, monospace)",
    fontSize: "10px",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    padding: "4px 12px",
    border: "1px solid",
    borderRadius: "3px",
    cursor: "pointer",
    whiteSpace: "nowrap",
    textAlign: "center",
    transition: "color 0.15s, border-color 0.15s, background 0.15s",
  };

  const inactiveStyle: React.CSSProperties = {
    color: "var(--graphite, rgba(28, 27, 24, 0.60))",
    borderColor: "var(--rule, rgba(28, 27, 24, 0.12))",
    background: "transparent",
  };

  const activeStyle: React.CSSProperties = {
    color: "var(--ink, #1C1B18)",
    borderColor: "var(--rule-emphasis, rgba(28, 27, 24, 0.20))",
    background: "var(--board, rgba(244, 243, 239, 0.40))",
  };

  return (
    <button
      type="button"
      onClick={onToggle}
      style={{
        ...baseStyle,
        ...(isActive ? activeStyle : inactiveStyle),
      }}
      title={
        isActive
          ? "Exit Quiet mode (show temporal controls)"
          : "Enter Quiet mode (hide temporal controls)"
      }
    >
      Quiet
    </button>
  );
}
