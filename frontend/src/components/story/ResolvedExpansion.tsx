// ─── Resolved Expansion ──────────────────────────────────────────
// Expansion content for a resolved conflict or acknowledged change.
// DS-2 §4.3: Post-resolution display with completed story.
//
// Layout:
//   ✓ CONFLICT · ACCEPTED · CD
//   [Source A]  [value A]    (stamp if matches resolution, redline-muted if not)
//   [Source B]  [value B]    (stamp if matches resolution, redline-muted if not)
//   ─────────────────────────────────
//   [ResolutionStamp]
//   ─────────────────────────────────
//   ● (blue) Source A → update to 60 min
//            directive · pending            ›

import { ResolutionStamp } from "./ResolutionStamp";
import { DirectiveSubRow } from "./DirectiveSubRow";

/** A source in the original disagreement. */
export interface ResolvedSource {
  sourceId: string;
  sourceName: string;
  value: unknown;
  /** Was this the chosen source in the resolution? */
  isChosen: boolean;
}

/** A directive spawned by the resolution. */
export interface ResolvedDirective {
  directiveId: string;
  targetSourceName: string;
  propertyName: string;
  targetValue: string | null;
  status: string;
}

interface ResolvedExpansionProps {
  /** The property name. */
  propertyName: string;
  /** Type of the resolved item. */
  itemType: "conflict" | "change";
  /** Context label (e.g., "CD"). */
  contextLabel?: string;
  /** From/to context names for changes. */
  fromContextName?: string;
  toContextName?: string;
  /** The sources involved in the original disagreement. */
  sources?: ResolvedSource[];
  /** Resolution stamp data. */
  resolution?: {
    chosenValue: string;
    chosenSourceName?: string;
    decidedBy?: string;
    method?: string;
    date?: string;
  };
  /** Spawned directives (for conflicts). */
  directives?: ResolvedDirective[];
  /** Navigate handler. */
  onNavigate?: (itemId: string) => void;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

export function ResolvedExpansion({
  propertyName: _propertyName,
  itemType,
  contextLabel,
  fromContextName,
  toContextName,
  sources,
  resolution,
  directives,
  onNavigate,
}: ResolvedExpansionProps) {
  const typeLabel = itemType === "conflict" ? "CONFLICT" : "CHANGE";
  const statusVerb = itemType === "conflict" ? "ACCEPTED" : "ACCEPTED";
  const contextDisplay = itemType === "change" && fromContextName && toContextName
    ? `${fromContextName} → ${toContextName}`
    : contextLabel;

  return (
    <div className="space-y-3">
      {/* Status line with checkmark */}
      <div className="flex items-center gap-2 text-xs">
        <svg className="w-3 h-3 text-stamp shrink-0" viewBox="0 0 12 12" fill="none">
          <path
            d="M2.5 6l2.5 2.5 4.5-4.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="font-mono uppercase text-stamp">{typeLabel}</span>
        <span className="text-trace">·</span>
        <span className="font-mono uppercase text-stamp">{statusVerb}</span>
        {contextDisplay && (
          <>
            <span className="text-trace">·</span>
            <span className="text-graphite">{contextDisplay}</span>
          </>
        )}
      </div>

      {/* Original disagreement — values matching the resolution are green,
           values that need to change are red. Custom resolution = both red. */}
      {sources && sources.length > 0 && (
        <div className="space-y-1">
          {sources.map((source) => {
            const valueStr = formatValue(source.value);
            const matchesResolution = resolution
              ? valueStr === resolution.chosenValue
              : source.isChosen;
            return (
              <div
                key={source.sourceId}
                className="grid grid-cols-[100px_1fr] gap-x-3 items-baseline"
              >
                <span className={`text-xs truncate ${
                  matchesResolution ? "text-stamp" : "text-redline/50"
                }`}>
                  {source.sourceName}
                </span>
                <span className={`text-sm font-mono ${
                  matchesResolution ? "text-stamp" : "text-redline/50"
                }`}>
                  {valueStr}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Resolution stamp */}
      {resolution && (
        <ResolutionStamp
          chosenValue={resolution.chosenValue}
          chosenSourceName={resolution.chosenSourceName}
          decidedBy={resolution.decidedBy}
          method={resolution.method}
          date={resolution.date}
        />
      )}

      {/* Directive sub-rows */}
      {directives && directives.length > 0 && (
        <div className="space-y-1">
          {directives.map((d) => (
            <DirectiveSubRow
              key={d.directiveId}
              directiveId={d.directiveId}
              targetSourceName={d.targetSourceName}
              propertyName={d.propertyName}
              targetValue={d.targetValue}
              status={d.status}
              present={true}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
    </div>
  );
}
