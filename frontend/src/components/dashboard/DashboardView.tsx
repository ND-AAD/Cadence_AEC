// ─── Dashboard View ──────────────────────────────────────────────
// Project-level dashboard with interactive rollups.
// DS-2 §11: Dashboard as navigation surface.
//
// Shows:
//   - Status breakdown: N needs review · N in review · N needs action
//   - By-type breakdown: Conflicts, Changes, Directives
//   - By-property rollup: Each property with counts (all clickable)

import { PropertyRollupCard } from "./PropertyRollupCard";

interface DashboardViewProps {
  /** Total conflicts pending. */
  conflictsPending: number;
  /** Total changes pending. */
  changesPending: number;
  /** Total directives pending. */
  directivesPending: number;
  /** Total action items. */
  totalActionItems: number;
  /** Breakdown by property: { property_name: { conflicts: N, changes: N } } */
  byProperty: Record<string, Record<string, number>>;
  /** Navigate handler (for clicking counts). */
  onNavigate: (itemId: string) => void;
}

export function DashboardView({
  conflictsPending,
  changesPending,
  directivesPending,
  totalActionItems,
  byProperty,
  onNavigate,
}: DashboardViewProps) {
  const propertyEntries = Object.entries(byProperty);

  return (
    <div className="bg-sheet min-h-full px-4 py-4 space-y-6">
      {/* Status overview */}
      <div>
        <h2 className="text-xs font-mono uppercase text-graphite tracking-wider mb-3">
          Project Status
        </h2>
        <div className="flex items-center gap-4 flex-wrap">
          <StatusBadge
            count={totalActionItems}
            label="action items"
            colorClass="text-ink"
          />
          <span className="text-trace">·</span>
          <StatusBadge
            count={conflictsPending}
            label="conflicts"
            colorClass="text-redline"
          />
          <StatusBadge
            count={changesPending}
            label="changes"
            colorClass="text-pencil"
          />
          <StatusBadge
            count={directivesPending}
            label="directives"
            colorClass="text-overlay"
          />
        </div>
      </div>

      {/* By-property rollups */}
      {propertyEntries.length > 0 && (
        <div>
          <h2 className="text-xs font-mono uppercase text-graphite tracking-wider mb-3">
            By Property
          </h2>
          <div className="grid grid-cols-1 gap-2">
            {propertyEntries.map(([propertyName, counts]) => (
              <PropertyRollupCard
                key={propertyName}
                propertyName={propertyName}
                conflicts={counts.conflicts ?? 0}
                changes={counts.changes ?? 0}
                directives={counts.directives ?? 0}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {totalActionItems === 0 && (
        <div className="flex items-center justify-center py-8">
          <p className="text-sm text-trace">
            No active workflow items. All clear.
          </p>
        </div>
      )}
    </div>
  );
}

// ─── Helper Components ──────────────────────────────────────────

function StatusBadge({
  count,
  label,
  colorClass,
}: {
  count: number;
  label: string;
  colorClass: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span className={`font-mono font-semibold ${colorClass}`}>{count}</span>
      <span className="text-graphite">{label}</span>
    </span>
  );
}
