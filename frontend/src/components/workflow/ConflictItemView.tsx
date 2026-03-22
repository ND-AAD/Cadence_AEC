// ─── Conflict Item View (Surface 2) ──────────────────────────────
// Full workflow item view for conflicts.
// DS-2 §5.1/5.2: Reached via pip click (page turn from property row).
//
// Unresolved:
//   Header: Fire Rating   CONFLICT · Needs Review
//   Disagreement grid: sources as columns
//   Resolution form (full — rationale, decided-by, note)
//
// Resolved:
//   Settled disagreement in trace colors
//   Non-chosen source in redline-muted (stale value treatment)
//   Resolution section with stamp
//   Directive connection rows

import { useCallback } from "react";
import type { ItemResponse } from "@/types/navigation";
import type { ResolutionMethod } from "@/api/actionItems";
import { resolveConflict } from "@/api/actionItems";
import { startReview, holdItem, resumeReview } from "@/api/workflow";
import { ResolutionForm, type ResolutionSource } from "./ResolutionForm";
import { ResolutionStamp } from "../story/ResolutionStamp";
import { DirectiveSubRow } from "../story/DirectiveSubRow";

interface ConflictItemViewProps {
  /** The conflict item from the API. */
  item: ItemResponse;
  /** The sources involved in the conflict. */
  sources: ResolutionSource[];
  /** Context label (e.g., "CD"). */
  contextLabel?: string;
  /** Resolution data (if resolved). */
  resolution?: {
    chosenValue: string;
    chosenSourceId: string;
    chosenSourceName?: string;
    decidedBy?: string;
    method?: string;
    date?: string;
  };
  /** Spawned directives (if resolved). */
  directives?: Array<{
    directiveId: string;
    targetSourceName: string;
    propertyName: string;
    targetValue: string | null;
    status: string;
  }>;
  /** Navigate handler. */
  onNavigate: (itemId: string) => void;
  /** Callback after workflow action to refresh data. */
  onWorkflowAction?: () => void;
}

/** Map backend status to UX label. */
function statusLabel(status: string): string {
  switch (status) {
    case "detected": return "Needs Review";
    case "in_review": return "In Review";
    case "hold": return "Hold";
    case "resolved": return "Accepted";
    default: return status;
  }
}

/** Map backend status to badge color class. */
function statusClass(status: string): string {
  switch (status) {
    case "detected":
    case "in_review":
      return "text-redline";
    case "hold":
      return "text-filed";
    case "resolved":
      return "text-stamp";
    default:
      return "text-graphite";
  }
}

export function ConflictItemView({
  item,
  sources,
  contextLabel,
  resolution,
  directives,
  onNavigate,
  onWorkflowAction,
}: ConflictItemViewProps) {
  const status = (item.properties?.status as string) ?? "detected";
  const propertyName = (item.properties?.property_name as string) ?? "Property";
  const isResolved = status === "resolved";

  // ── API handlers ──
  const handleStartReview = useCallback(async () => {
    try {
      await startReview(item.id);
      onWorkflowAction?.();
    } catch (err) {
      console.error("Failed to start review:", err);
    }
  }, [item.id, onWorkflowAction]);

  const handleResolve = useCallback(async (request: {
    chosen_value: string | null;
    chosen_source_id: string | null;
    method: ResolutionMethod;
    rationale: string;
    decided_by: string;
    note?: string;
  }) => {
    try {
      await resolveConflict(item.id, {
        chosen_value: request.chosen_value,
        chosen_source_id: request.chosen_source_id,
        method: request.method,
        rationale: request.rationale,
        decided_by: request.decided_by,
      });
      onWorkflowAction?.();
    } catch (err) {
      console.error("Failed to resolve conflict:", err);
    }
  }, [item.id, onWorkflowAction]);

  const handleHold = useCallback(async () => {
    try {
      await holdItem(item.id);
      onWorkflowAction?.();
    } catch (err) {
      console.error("Failed to hold:", err);
    }
  }, [item.id, onWorkflowAction]);

  const handleResume = useCallback(async () => {
    try {
      await resumeReview(item.id);
      onWorkflowAction?.();
    } catch (err) {
      console.error("Failed to resume:", err);
    }
  }, [item.id, onWorkflowAction]);

  return (
    <div className="bg-sheet min-h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-rule">
        <div className="flex items-baseline justify-between">
          <h1 className="text-sm font-medium text-ink">{propertyName}</h1>
          <div className="flex items-center gap-2 text-xs">
            <span className={`font-mono uppercase ${statusClass(status)}`}>
              CONFLICT
            </span>
            <span className="text-trace">·</span>
            <span className={`font-mono ${statusClass(status)}`}>
              {statusLabel(status)}
            </span>
            {contextLabel && (
              <>
                <span className="text-trace">·</span>
                <span className="text-graphite">{contextLabel}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Disagreement grid */}
      <div className="px-4 py-3 border-b border-rule">
        {/* Column headers */}
        <div className="grid grid-cols-[120px_repeat(2,1fr)] gap-x-3 mb-2">
          <div /> {/* Empty label column */}
          {sources.map((source) => (
            <button
              key={source.sourceId}
              type="button"
              className={`text-xs font-mono uppercase truncate text-left transition-colors duration-100 ${
                isResolved ? "text-graphite" : "text-redline-ink"
              }`}
              onClick={() => onNavigate(source.sourceId)}
              title={`Navigate to ${source.sourceName}`}
            >
              {source.sourceName}
            </button>
          ))}
        </div>

        {/* Value row */}
        <div className={`grid grid-cols-[120px_repeat(2,1fr)] gap-x-3 items-start px-0 min-h-[34px] py-[7px] ${
          isResolved ? "" : "border-l-2 border-l-redline"
        }`}>
          <span className="text-graphite text-xs leading-[20px] truncate pl-2">
            {propertyName}
          </span>
          {sources.map((source) => {
            // Stale value treatment: non-chosen source in redline-muted
            const isChosen = resolution?.chosenSourceId === source.sourceId;
            const valueClass = isResolved
              ? isChosen
                ? "text-trace"
                : "text-redline/50"
              : "text-redline-ink font-medium";

            return (
              <span key={source.sourceId} className={`font-mono text-sm ${valueClass}`}>
                {source.value}
              </span>
            );
          })}
        </div>
      </div>

      {/* Resolution stamp (when resolved) */}
      {isResolved && resolution && (
        <div className="px-4 py-3 border-b border-rule bg-stamp-wash border-l-2 border-l-stamp">
          <div className="flex items-center gap-2 text-xs mb-2">
            <svg className="w-3 h-3 text-stamp shrink-0" viewBox="0 0 12 12" fill="none">
              <path d="M2.5 6l2.5 2.5 4.5-4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="font-mono uppercase text-stamp">Resolved</span>
          </div>
          <ResolutionStamp
            chosenValue={resolution.chosenValue}
            chosenSourceName={resolution.chosenSourceName}
            decidedBy={resolution.decidedBy}
            method={resolution.method}
            date={resolution.date}
          />
        </div>
      )}

      {/* Directive connections (when resolved) */}
      {isResolved && directives && directives.length > 0 && (
        <div className="px-4 py-3 border-b border-rule">
          <div className="text-xs text-graphite font-mono uppercase mb-2">Directives</div>
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
        </div>
      )}

      {/* Resolution form (when unresolved or held) */}
      {!isResolved && (
        <div className="px-4 py-4">
          <ResolutionForm
            sources={sources}
            status={status}
            onStartReview={status === "detected" ? handleStartReview : undefined}
            onResolve={handleResolve}
            onHold={status !== "hold" ? handleHold : undefined}
            onResume={status === "hold" ? handleResume : undefined}
          />
        </div>
      )}
    </div>
  );
}
