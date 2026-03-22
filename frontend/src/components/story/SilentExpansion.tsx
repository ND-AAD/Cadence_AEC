// ─── Silent Expansion ────────────────────────────────────────────
// Expansion content for aligned (silent) properties.
// DS-2 §4.3: Shows source attribution — which sources describe
// this property. Each source is a navigable red string.
//
// "Silence" is about decoration, not data. The value always shows.
// Sources are discoverable on expand for audit purposes.

interface SilentExpansionProps {
  /** Source names and IDs that agree on this property. */
  sources: Array<{ sourceId: string; sourceName: string }>;
  /** Navigate to a source item (red string → Z-axis shift). */
  onNavigate?: (sourceId: string) => void;
}

export function SilentExpansion({
  sources,
  onNavigate,
}: SilentExpansionProps) {
  if (sources.length === 0) {
    return (
      <div className="text-xs text-trace">
        No sources recorded for this property.
      </div>
    );
  }

  return (
    <div className="text-xs">
      <span className="text-graphite">Sources: </span>
      {sources.map((source, i) => (
        <span key={source.sourceId}>
          {i > 0 && <span className="text-trace">, </span>}
          <button
            type="button"
            className="text-redline hover:text-redline-ink transition-colors duration-100"
            onClick={(e) => {
              e.stopPropagation();
              onNavigate?.(source.sourceId);
            }}
            title={`Navigate to ${source.sourceName}`}
          >
            {source.sourceName}
          </button>
        </span>
      ))}
    </div>
  );
}
