// ─── Resolution Stamp ────────────────────────────────────────────
// Compact display of a conflict resolution decision.
// DS-2 §4.4: Mini-resolution stamp inside row expansion.
//
// Layout:
//   ─────────────────────────────────
//   60 min  from Door Schedule
//   J. Martinez · field verification · 2026-01-20
//   ─────────────────────────────────

interface ResolutionStampProps {
  /** The chosen/resolved value. */
  chosenValue: string;
  /** Name of the source whose value was chosen. */
  chosenSourceName?: string;
  /** Who made the decision. */
  decidedBy?: string;
  /** Resolution method (e.g., "field verification"). */
  method?: string;
  /** Date of the decision (ISO string). */
  date?: string;
}

export function ResolutionStamp({
  chosenValue,
  chosenSourceName,
  decidedBy,
  method,
  date,
}: ResolutionStampProps) {
  // Format date if provided.
  const formattedDate = date
    ? new Date(date).toLocaleDateString("en-CA") // YYYY-MM-DD format
    : null;

  // Build metadata line: "J. Martinez · field verification · 2026-01-20"
  const metaParts: string[] = [];
  if (decidedBy) metaParts.push(decidedBy);
  if (method) metaParts.push(method);
  if (formattedDate) metaParts.push(formattedDate);
  const metaLine = metaParts.join(" · ");

  return (
    <div className="py-2">
      {/* Top border */}
      <div className="border-t border-rule mb-2" />

      {/* Value + source */}
      <div className="flex items-baseline gap-2">
        <span className="text-sm text-stamp-ink font-medium font-mono">
          {chosenValue}
        </span>
        {chosenSourceName && (
          <span className="text-xs text-graphite">
            from {chosenSourceName}
          </span>
        )}
      </div>

      {/* Metadata line */}
      {metaLine && (
        <div className="text-xs text-trace font-mono mt-0.5">
          {metaLine}
        </div>
      )}

      {/* Bottom border */}
      <div className="border-b border-rule mt-2" />
    </div>
  );
}
