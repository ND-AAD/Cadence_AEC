import { useState, useCallback } from "react";
import { MilestoneCombobox } from "./MilestoneCombobox";
import { SourceCombobox } from "./SourceCombobox";
import { FileDropZone } from "./FileDropZone";
import { MappingReview } from "./MappingReview";
import { ImportProgress } from "./ImportProgress";
import { analyzeFile, confirmMapping, runImport, type ProposedMappingResponse, type ImportResult } from "@/api/import";
import { apiDelete } from "@/api/client";

type ModalPhase = "form" | "review" | "progress" | "error";

interface AddDataModalProps {
  projectId: string;
  prefillMilestoneId?: string;
  prefillSourceId?: string;
  onClose: () => void;
  onImportComplete: (result: ImportResult) => void;
}

export function AddDataModal({
  projectId,
  onClose,
  onImportComplete,
}: AddDataModalProps) {
  const [phase, setPhase] = useState<ModalPhase>("form");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorReturnPhase, setErrorReturnPhase] = useState<ModalPhase>("form");

  // Form state
  const [milestone, setMilestone] = useState<{ id: string; name: string } | null>(null);
  const [source, setSource] = useState<{ id: string; name: string } | null>(null);
  const [file, setFile] = useState<File | null>(null);

  // Track items created during this flow (for cleanup on cancel).
  const [createdItemIds, setCreatedItemIds] = useState<string[]>([]);

  const trackCreatedItem = useCallback((id: string) => {
    setCreatedItemIds((prev) => [...prev, id]);
  }, []);

  /** Delete any items created during this modal flow (milestone, source). */
  const cleanupCreatedItems = useCallback(async () => {
    for (const id of createdItemIds) {
      try {
        await apiDelete(`/v1/items/${id}`);
      } catch {
        // Best-effort cleanup — item may already be gone or in use.
      }
    }
  }, [createdItemIds]);

  // Analyze result (passed to MappingReview in OB-6)
  const [proposal, setProposal] = useState<ProposedMappingResponse | null>(null);

  // Progress tracking
  const [progressSteps, setProgressSteps] = useState<Array<{ label: string; status: "pending" | "active" | "done" }>>([]);
  const [progressSummary, setProgressSummary] = useState<string | null>(null);

  const canSubmit = milestone && source && file;

  async function handleSubmit() {
    if (!canSubmit || !file || !source) return;
    try {
      const result = await analyzeFile(file, source.id, projectId);
      setProposal(result);
      setPhase("review");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to analyze file");
      setErrorReturnPhase("form");
      setPhase("error");
    }
  }

  /** Cancel: clean up any items created during this flow, then close. */
  const handleCancel = useCallback(async () => {
    await cleanupCreatedItems();
    onClose();
  }, [cleanupCreatedItems, onClose]);

  // Handle backdrop click
  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget) handleCancel();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/20"
      onClick={handleBackdropClick}
    >
      <div className="bg-sheet border border-rule w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-rule">
          <h2 className="text-sm font-semibold text-ink">Add Data</h2>
          <button
            onClick={handleCancel}
            className="text-graphite hover:text-ink transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-5">
          {phase === "form" && (
            <>
              {/* Milestone */}
              <div>
                <label className="block text-xs font-medium text-graphite mb-1.5">
                  Milestone
                </label>
                <MilestoneCombobox
                  projectId={projectId}
                  value={milestone}
                  onChange={setMilestone}
                  onItemCreated={trackCreatedItem}
                />
              </div>

              {/* Source */}
              <div>
                <label className="block text-xs font-medium text-graphite mb-1.5">
                  Source
                </label>
                <SourceCombobox
                  projectId={projectId}
                  value={source}
                  onChange={setSource}
                  onItemCreated={trackCreatedItem}
                />
              </div>

              {/* File */}
              <div>
                <label className="block text-xs font-medium text-graphite mb-1.5">
                  File
                </label>
                <FileDropZone
                  file={file}
                  onFileSelect={setFile}
                />
              </div>
            </>
          )}

          {phase === "review" && proposal && (
            <MappingReview
              proposal={proposal}
              onReanalyze={async () => {
                if (!file || !source) return;
                try {
                  const result = await analyzeFile(file, source.id, projectId);
                  setProposal(result);
                } catch (err) {
                  setErrorMessage(err instanceof Error ? err.message : "Re-analysis failed");
                  setErrorReturnPhase("review");
                  setPhase("error");
                }
              }}
              onConfirm={async (corrections, targetType) => {
                try {
                  const confirmed = await confirmMapping(proposal.proposal_id, corrections, targetType);
                  // Now run the actual import
                  if (!file || !source || !milestone) return;
                  setPhase("progress");

                  // Set up progress steps
                  const steps = [];
                  steps.push({ label: "Mapping confirmed", status: "done" as const });
                  steps.push({ label: "Importing items…", status: "active" as const });
                  setProgressSteps([...steps]);

                  const result = await runImport(
                    file,
                    source.id,
                    milestone.id,
                    confirmed.confirmed_config,
                  );

                  // Update progress
                  steps[steps.length - 1] = {
                    label: `Imported ${result.summary.items_imported} items`,
                    status: "done" as const,
                  };
                  if (result.summary.source_changes > 0) {
                    steps.push({
                      label: `${result.summary.source_changes} changes detected`,
                      status: "done" as const,
                    });
                  }
                  if (result.summary.new_conflicts > 0) {
                    steps.push({
                      label: `${result.summary.new_conflicts} new conflicts`,
                      status: "done" as const,
                    });
                  }
                  setProgressSteps([...steps]);
                  setProgressSummary(
                    `Import complete — ${result.summary.items_imported} items`
                  );

                  // Navigate after 2 seconds (A3)
                  await new Promise((resolve) => setTimeout(resolve, 2000));
                  onImportComplete(result);
                } catch (err) {
                  setErrorMessage(err instanceof Error ? err.message : "Import failed");
                  setErrorReturnPhase("review");
                  setPhase("error");
                }
              }}
              onCancel={handleCancel}
            />
          )}

          {phase === "progress" && (
            <ImportProgress
              steps={progressSteps}
              summary={progressSummary}
            />
          )}

          {phase === "error" && (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <p className="text-sm text-redline-ink mb-4">{errorMessage}</p>
              <button
                onClick={() => setPhase(errorReturnPhase)}
                className="px-3 py-1 text-xs font-medium text-graphite border border-rule"
              >
                Try Again
              </button>
            </div>
          )}
        </div>

        {/* Footer — only shown in form phase */}
        {phase === "form" && (
          <div className="flex justify-end gap-2 px-6 py-4 border-t border-rule">
            <button
              onClick={handleCancel}
              className="px-3 py-1.5 text-xs text-graphite border border-rule hover:text-ink transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="px-3 py-1.5 text-xs font-medium bg-ink text-sheet hover:bg-ink/90
                         transition-colors disabled:opacity-50"
            >
              Import
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
