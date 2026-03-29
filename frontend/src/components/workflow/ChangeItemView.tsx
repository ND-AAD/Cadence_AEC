// ─── Change Item View (Surface 2) ────────────────────────────────
// Full workflow item view for changes.
// DS-2 §5.3: Reached via pip click from change's amber pip.
//
// Breadcrumb: ... › Door 101 › Material: DD → CD
// Both values shown, source attribution, full action buttons.

import { useCallback, useState } from "react";
import type { ItemResponse } from "@/types/navigation";
import { acknowledgeChange, startReview, holdItem, resumeReview } from "@/api/workflow";
import { ItemNotes } from "../story/ItemNotes";

interface ChangeItemViewProps {
  /** The change item from the API. */
  item: ItemResponse;
  /** Property name that changed. */
  propertyName?: string;
  /** From context label (e.g., "DD"). */
  fromContextName?: string;
  /** To context label (e.g., "CD"). */
  toContextName?: string;
  /** Old value. */
  oldValue?: string;
  /** New value. */
  newValue?: string;
  /** Source name. */
  sourceName?: string;
  /** Navigate handler. */
  onNavigate: (itemId: string) => void;
  /** Callback after workflow action. */
  onWorkflowAction?: () => void;
  /** Current user name (for note authorship). */
  userName?: string;
}

function statusLabel(status: string): string {
  switch (status) {
    case "detected": return "Needs Review";
    case "in_review": return "In Review";
    case "hold": return "Hold";
    case "acknowledged": return "Accepted";
    default: return status;
  }
}

function statusClass(status: string): string {
  switch (status) {
    case "detected":
    case "in_review":
      return "text-pencil";
    case "hold":
      return "text-filed";
    case "acknowledged":
      return "text-stamp";
    default:
      return "text-graphite";
  }
}

export function ChangeItemView({
  item,
  propertyName,
  fromContextName,
  toContextName,
  oldValue,
  newValue,
  sourceName,
  onNavigate: _onNavigate,
  onWorkflowAction,
  userName,
}: ChangeItemViewProps) {
  const status = (item.properties?.status as string) ?? "detected";
  const displayProperty = propertyName ?? (item.properties?.property_name as string) ?? "Property";
  const isAcknowledged = status === "acknowledged";
  const isActive = status === "detected" || status === "in_review";
  const isHeld = status === "hold";

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartReview = useCallback(async () => {
    setError(null);
    setPending(true);
    try {
      await startReview(item.id);
      onWorkflowAction?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start review");
    } finally {
      setPending(false);
    }
  }, [item.id, onWorkflowAction]);

  const handleAcknowledge = useCallback(async () => {
    setError(null);
    setPending(true);
    try {
      await acknowledgeChange(item.id);
      onWorkflowAction?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to acknowledge change");
    } finally {
      setPending(false);
    }
  }, [item.id, onWorkflowAction]);

  const handleHold = useCallback(async () => {
    setError(null);
    setPending(true);
    try {
      await holdItem(item.id);
      onWorkflowAction?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to hold item");
    } finally {
      setPending(false);
    }
  }, [item.id, onWorkflowAction]);

  const handleResume = useCallback(async () => {
    setError(null);
    setPending(true);
    try {
      await resumeReview(item.id);
      onWorkflowAction?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resume review");
    } finally {
      setPending(false);
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
              CHANGE
            </span>
            <span className="text-trace">·</span>
            <span className={`font-mono ${statusClass(status)}`}>
              {statusLabel(status)}
            </span>
            {fromContextName && toContextName && (
              <>
                <span className="text-trace">·</span>
                <span className="text-graphite">
                  {fromContextName}
                  <span className="mx-1 text-trace">→</span>
                  {toContextName}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Value comparison */}
      <div className={`px-4 py-3 border-b border-rule ${isHeld ? "border-l-2 border-l-filed" : isAcknowledged ? "" : "border-l-2 border-l-pencil"}`}>
        <div className="space-y-2">
          {/* Old value */}
          {fromContextName && oldValue !== undefined && (
            <div className="grid grid-cols-[100px_1fr] gap-x-3 items-baseline">
              <span className={`text-xs truncate ${isHeld ? "text-filed" : "text-trace"}`}>
                {fromContextName}
              </span>
              <span className={`text-sm font-mono ${isHeld ? "text-filed" : "text-trace"}`}>
                {oldValue ?? "—"}
              </span>
            </div>
          )}

          {/* New value */}
          {toContextName && newValue !== undefined && (
            <div className="grid grid-cols-[100px_1fr] gap-x-3 items-baseline">
              <span className={`text-xs truncate ${isHeld ? "text-filed" : "text-pencil-ink"}`}>
                {toContextName}
              </span>
              <span className={`text-sm font-mono font-medium ${isHeld ? "text-filed" : "text-pencil-ink"}`}>
                {newValue ?? "—"}
              </span>
            </div>
          )}

          {/* Source attribution */}
          {sourceName && (
            <div className="text-xs text-graphite mt-2">
              Source: <span className="font-mono">{sourceName}</span>
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      {!isAcknowledged && (
        <div className="px-4 py-4">
          <div className="flex items-center gap-2">
            {/* Start Review */}
            {status === "detected" && (
              <button
                type="button"
                onClick={handleStartReview}
                disabled={pending}
                className="bg-transparent text-ink border border-rule-emphasis rounded text-xs px-3 py-1.5 hover:bg-board/20 hover:border-graphite transition-colors duration-100 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
              >
                Start Review
              </button>
            )}

            {/* Acknowledge */}
            {isActive && (
              <button
                type="button"
                onClick={handleAcknowledge}
                disabled={pending}
                className="bg-pencil-wash text-pencil-ink border border-pencil rounded text-xs px-3 py-1.5 hover:bg-pencil/10 transition-colors duration-100 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
              >
                Acknowledge
              </button>
            )}

            {/* Hold */}
            {isActive && (
              <button
                type="button"
                onClick={handleHold}
                disabled={pending}
                className="bg-transparent text-filed border border-rule-emphasis rounded text-xs px-3 py-1.5 hover:bg-filed-wash hover:border-filed transition-colors duration-100 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
              >
                Hold
              </button>
            )}

            {/* Resume */}
            {isHeld && (
              <button
                type="button"
                onClick={handleResume}
                disabled={pending}
                className="bg-transparent text-ink border border-rule-emphasis rounded text-xs px-3 py-1.5 hover:bg-board/20 hover:border-graphite transition-colors duration-100 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1"
              >
                Resume Review
              </button>
            )}
          </div>
          {error && (
            <div className="mt-3 text-xs text-redline">
              {error}
            </div>
          )}
        </div>
      )}

      {/* Acknowledged state */}
      {isAcknowledged && (
        <div className="px-4 py-4">
          <div className="flex items-center gap-2 text-xs text-stamp">
            <svg className="w-3 h-3 shrink-0" viewBox="0 0 12 12" fill="none">
              <path d="M2.5 6l2.5 2.5 4.5-4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="font-mono uppercase">Acknowledged</span>
          </div>
        </div>
      )}

      {/* Notes section (bottom of item view) */}
      <ItemNotes itemId={item.id} userName={userName} />
    </div>
  );
}
