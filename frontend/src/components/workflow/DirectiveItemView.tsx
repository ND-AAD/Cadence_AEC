// ─── Directive Item View (Surface 2) ─────────────────────────────
// Full workflow item view for directives.
// DS-2 §5.4: Reached via blue pip click from directive sub-row.
//
// Shows: obligation text, target value, target source, originating
// decision, affected item. Status: pending or fulfilled.

import { useCallback } from "react";
import type { ItemResponse } from "@/types/navigation";
import { holdItem, resumeReview } from "@/api/workflow";
import { fulfillDirective } from "@/api/actionItems";

interface DirectiveItemViewProps {
  /** The directive item from the API. */
  item: ItemResponse;
  /** Name of the target source (who needs to act). */
  targetSourceName?: string;
  /** The property being directed. */
  propertyName?: string;
  /** The target value to adopt. */
  targetValue?: string;
  /** The affected item identifier. */
  affectedItemName?: string;
  /** The affected item ID (for navigation). */
  affectedItemId?: string;
  /** The originating decision/conflict identifier. */
  decisionName?: string;
  /** The originating decision/conflict ID (for navigation). */
  decisionId?: string;
  /** Navigate handler. */
  onNavigate: (itemId: string) => void;
  /** Callback after workflow action. */
  onWorkflowAction?: () => void;
}

function statusLabel(status: string): string {
  switch (status) {
    case "pending": return "Pending";
    case "fulfilled": return "Fulfilled";
    case "hold": return "Hold";
    case "superseded": return "Superseded";
    default: return status;
  }
}

function statusClass(status: string): string {
  switch (status) {
    case "pending": return "text-overlay";
    case "fulfilled": return "text-stamp";
    case "hold": return "text-filed";
    default: return "text-graphite";
  }
}

export function DirectiveItemView({
  item,
  targetSourceName,
  propertyName,
  targetValue,
  affectedItemName,
  affectedItemId,
  decisionName,
  decisionId,
  onNavigate,
  onWorkflowAction,
}: DirectiveItemViewProps) {
  const status = (item.properties?.status as string) ?? "pending";
  const displayProperty = propertyName ?? (item.properties?.property_name as string) ?? "Property";
  const displayTarget = targetSourceName ?? "Source";
  const displayValue = targetValue ?? (item.properties?.target_value as string) ?? "—";

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

  const handleFulfill = useCallback(async () => {
    try {
      await fulfillDirective(item.id);
      onWorkflowAction?.();
    } catch (err) {
      console.error("Failed to fulfill:", err);
    }
  }, [item.id, onWorkflowAction]);

  return (
    <div className="bg-sheet min-h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-rule">
        <div className="flex items-baseline justify-between">
          <h1 className="text-sm font-medium text-ink">{displayProperty}</h1>
          <div className="flex items-center gap-2 text-xs">
            <span className={`font-mono uppercase ${statusClass(status)}`}>
              DIRECTIVE
            </span>
            <span className="text-trace">·</span>
            <span className={`font-mono ${statusClass(status)}`}>
              {statusLabel(status)}
            </span>
          </div>
        </div>
      </div>

      {/* Obligation */}
      <div className={`px-4 py-3 border-b border-rule ${
        status === "hold" ? "border-l-2 border-l-filed" : "border-l-2 border-l-overlay"
      }`}>
        <div className="space-y-3">
          {/* Obligation text */}
          <div className="text-sm">
            <span className={`font-medium ${status === "hold" ? "text-filed" : "text-overlay"}`}>
              {displayTarget}
            </span>
            <span className="text-graphite"> → update </span>
            <span className="text-ink">{displayProperty}</span>
            <span className="text-graphite"> to </span>
            <span className="font-mono text-ink font-medium">{displayValue}</span>
          </div>

          {/* Affected item (navigable) */}
          {affectedItemId && affectedItemName && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-graphite">Affected item:</span>
              <button
                type="button"
                className="text-ink hover:text-redline transition-colors duration-100"
                onClick={() => onNavigate(affectedItemId)}
              >
                {affectedItemName}
              </button>
              <span className="text-trace">›</span>
            </div>
          )}

          {/* Originating decision (navigable) */}
          {decisionId && decisionName && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-graphite">From decision:</span>
              <button
                type="button"
                className="text-ink hover:text-redline transition-colors duration-100"
                onClick={() => onNavigate(decisionId)}
              >
                {decisionName}
              </button>
              <span className="text-trace">›</span>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      {status !== "fulfilled" && status !== "superseded" && (
        <div className="px-4 py-4">
          <div className="flex items-center gap-2">
            {/* Manual fulfill (for testing / edge cases) */}
            {status === "pending" && (
              <button
                type="button"
                onClick={handleFulfill}
                className="bg-stamp-wash text-stamp-ink border border-stamp rounded text-xs px-3 py-1.5 hover:bg-stamp/10 transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
              >
                Mark Fulfilled
              </button>
            )}

            {/* Hold */}
            {status === "pending" && (
              <button
                type="button"
                onClick={handleHold}
                className="bg-transparent text-filed border border-rule-emphasis rounded text-xs px-3 py-1.5 hover:bg-filed-wash hover:border-filed transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
              >
                Hold
              </button>
            )}

            {/* Resume */}
            {status === "hold" && (
              <button
                type="button"
                onClick={handleResume}
                className="bg-transparent text-ink border border-rule-emphasis rounded text-xs px-3 py-1.5 hover:bg-board/20 hover:border-graphite transition-colors duration-100 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
              >
                Resume
              </button>
            )}
          </div>
        </div>
      )}

      {/* Fulfilled state */}
      {status === "fulfilled" && (
        <div className="px-4 py-4">
          <div className="flex items-center gap-2 text-xs text-stamp">
            <svg className="w-3 h-3 shrink-0" viewBox="0 0 12 12" fill="none">
              <path d="M2.5 6l2.5 2.5 4.5-4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="font-mono uppercase">Fulfilled</span>
          </div>
        </div>
      )}
    </div>
  );
}
