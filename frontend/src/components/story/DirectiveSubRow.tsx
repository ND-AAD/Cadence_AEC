// ─── Directive Sub-Row ───────────────────────────────────────────
// Sub-row inside a resolved expansion showing a spawned directive.
// DS-2 §4.5: Blue pip + obligation text + status badge.
//
// Layout:
//   ● (blue)  Finish Schedule → update fire_rating to 60 min
//              directive · pending                           ›

import { Pip } from "./Pip";

interface DirectiveSubRowProps {
  /** Directive item ID (for navigation). */
  directiveId: string;
  /** Name of the target source (who needs to act). */
  targetSourceName: string;
  /** The property being directed. */
  propertyName: string;
  /** The target value to adopt. */
  targetValue: string | null;
  /** Directive status: pending, fulfilled, or hold. */
  status: string;
  /** Whether the directive is at the current context (filled) or nearby (hollow). */
  present?: boolean;
  /** Navigate to the directive item (pip click = page turn). */
  onNavigate?: (directiveId: string) => void;
}

function statusBadge(status: string): { label: string; className: string } {
  switch (status) {
    case "pending":
      return { label: "pending", className: "text-overlay" };
    case "fulfilled":
      return { label: "fulfilled", className: "text-stamp" };
    case "hold":
      return { label: "hold", className: "text-filed" };
    default:
      return { label: status, className: "text-graphite" };
  }
}

export function DirectiveSubRow({
  directiveId,
  targetSourceName,
  propertyName,
  targetValue,
  status,
  present = true,
  onNavigate,
}: DirectiveSubRowProps) {
  const badge = statusBadge(status);

  return (
    <div className="flex items-start gap-2 py-1">
      {/* Blue pip */}
      <div className="shrink-0 mt-0.5">
        <Pip
          filled={present}
          color={status === "hold" ? "filed" : "overlay"}
          tooltip={`Directive: ${targetSourceName} → update ${propertyName}`}
          onClick={onNavigate ? () => onNavigate(directiveId) : undefined}
        />
      </div>

      {/* Obligation text */}
      <div className="flex-1 min-w-0">
        <div className="text-sm">
          <span className="text-overlay font-medium">{targetSourceName}</span>
          <span className="text-graphite"> → update </span>
          <span className="text-ink">{propertyName}</span>
          {targetValue && (
            <>
              <span className="text-graphite"> to </span>
              <span className="font-mono text-ink">{targetValue}</span>
            </>
          )}
        </div>
        <div className="text-xs text-trace mt-0.5">
          <span>directive</span>
          <span className="mx-1">·</span>
          <span className={badge.className}>{badge.label}</span>
        </div>
      </div>

      {/* Navigation chevron */}
      {onNavigate && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onNavigate(directiveId);
          }}
          className="shrink-0 text-trace hover:text-ink transition-colors duration-100 text-sm px-1"
          title="Navigate to directive"
        >
          ›
        </button>
      )}
    </div>
  );
}
