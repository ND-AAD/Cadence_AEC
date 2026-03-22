// ─── Property Rollup Card ────────────────────────────────────────
// DS-2 §11.1: Individual property rollup in dashboard.
// Property name is clickable → navigates to property item.
// Count badges are interactive → navigate to filtered views.

interface PropertyRollupCardProps {
  /** Property name (e.g., "fire_rating"). */
  propertyName: string;
  /** Conflict count for this property. */
  conflicts: number;
  /** Change count for this property. */
  changes: number;
  /** Directive count for this property. */
  directives: number;
  /** Navigate handler. */
  onNavigate: (itemId: string) => void;
}

export function PropertyRollupCard({
  propertyName,
  conflicts,
  changes,
  directives,
  onNavigate,
}: PropertyRollupCardProps) {
  const total = conflicts + changes + directives;
  if (total === 0) return null;

  return (
    <div className="flex items-center justify-between px-3 py-2 rounded border border-rule hover:bg-board/20 transition-colors duration-100">
      {/* Property name (clickable → property item) */}
      <button
        type="button"
        className="text-sm text-ink hover:text-redline transition-colors duration-100 font-medium"
        onClick={() => {
          // Navigate to the property item.
          // The property item ID follows the pattern: {type}/{property_name}
          // TODO: Resolve property item ID from the graph.
          onNavigate(propertyName);
        }}
        title={`Navigate to ${propertyName}`}
      >
        {propertyName.replace(/_/g, " ")}
      </button>

      {/* Count badges */}
      <div className="flex items-center gap-3">
        {conflicts > 0 && (
          <span className="inline-flex items-center gap-1 text-xs">
            <span className="w-[7px] h-[7px] rounded-full bg-redline" />
            <span className="font-mono text-redline">{conflicts}</span>
          </span>
        )}
        {changes > 0 && (
          <span className="inline-flex items-center gap-1 text-xs">
            <span className="w-[7px] h-[7px] rounded-full bg-pencil" />
            <span className="font-mono text-pencil">{changes}</span>
          </span>
        )}
        {directives > 0 && (
          <span className="inline-flex items-center gap-1 text-xs">
            <span className="w-[7px] h-[7px] rounded-full bg-overlay" />
            <span className="font-mono text-overlay">{directives}</span>
          </span>
        )}
      </div>
    </div>
  );
}
