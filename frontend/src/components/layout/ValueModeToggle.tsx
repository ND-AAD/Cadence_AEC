// ─── Value Mode Toggle ──────────────────────────────────────
// Submitted / Cumulative text toggle for breadcrumb bar.
// Per DS-2 Addendum v3 §2.3.
//
// Two text labels, no container. Active word: bold ink.
// Inactive word: normal graphite, hover to ink.
// Separator: subtle middot.
// Disabled in Quiet mode (both words render trace, non-interactive).
// Persists across navigation.
//
// DTC-3: Value mode no longer auto-switches based on comparison state.

interface ValueModeToggleProps {
  value: "submitted" | "cumulative";
  onChange: (mode: "submitted" | "cumulative") => void;
  disabled?: boolean; // True in Quiet mode
}

export function ValueModeToggle({
  value,
  onChange,
  disabled = false,
}: ValueModeToggleProps) {
  const wordStyle = (isActive: boolean): React.CSSProperties => ({
    fontFamily: "var(--font-mono, ui-monospace, monospace)",
    fontSize: "10px",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    fontWeight: isActive ? 600 : 400,
    color: disabled
      ? "var(--trace, rgba(28, 27, 24, 0.30))"
      : isActive
        ? "var(--ink, #1C1B18)"
        : "var(--graphite, rgba(28, 27, 24, 0.60))",
    cursor: disabled ? "default" : isActive ? "default" : "pointer",
    padding: "0 4px",
    whiteSpace: "nowrap",
    transition: "color 0.15s",
    background: "transparent",
    border: "none",
  });

  const handleSubmitted = () => {
    if (!disabled && value !== "submitted") onChange("submitted");
  };

  const handleCumulative = () => {
    if (!disabled && value !== "cumulative") onChange("cumulative");
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "2px",
        fontSize: "10px",
      }}
    >
      <button
        type="button"
        onClick={handleSubmitted}
        disabled={disabled}
        style={wordStyle(value === "submitted")}
        onMouseEnter={(e) => {
          if (!disabled && value !== "submitted") {
            (e.currentTarget as HTMLButtonElement).style.color =
              "var(--ink, #1C1B18)";
          }
        }}
        onMouseLeave={(e) => {
          if (!disabled && value !== "submitted") {
            (e.currentTarget as HTMLButtonElement).style.color =
              "var(--graphite, rgba(28, 27, 24, 0.60))";
          }
        }}
        title="Show submitted values only"
      >
        Submitted
      </button>

      <span
        style={{
          color: disabled ? "var(--trace)" : "var(--graphite)",
          fontSize: "10px",
        }}
      >
        ·
      </span>

      <button
        type="button"
        onClick={handleCumulative}
        disabled={disabled}
        style={wordStyle(value === "cumulative")}
        onMouseEnter={(e) => {
          if (!disabled && value !== "cumulative") {
            (e.currentTarget as HTMLButtonElement).style.color =
              "var(--ink, #1C1B18)";
          }
        }}
        onMouseLeave={(e) => {
          if (!disabled && value !== "cumulative") {
            (e.currentTarget as HTMLButtonElement).style.color =
              "var(--graphite, rgba(28, 27, 24, 0.60))";
          }
        }}
        title="Show cumulative (carried-forward) values"
      >
        Cumulative
      </button>
    </div>
  );
}
