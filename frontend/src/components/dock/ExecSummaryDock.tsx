// ─── Exec Summary Dock ────────────────────────────────────────────
// Right-side dockable panel showing project-level health tree.
// DS-1 §7: Project health that persists regardless of navigation depth.
// system.md: Three-level navigable tree (Category → Type → Instance).
// Toggle lives outside in LayoutFrame — panel is pure content.

import type { DockCategory, ImportSummaryResponse } from "@/types/dashboard";
import { DockCategoryRow } from "./DockCategoryRow";
import { DockTypeRow } from "./DockTypeRow";
import { DockImportBar } from "./DockImportBar";
import { NotesArea } from "./NotesArea";
import { QuietButton } from "./QuietButton";
import { useNotes } from "@/hooks/useNotes";

interface ExecSummaryDockProps {
  isOpen: boolean;
  categories: DockCategory[];
  importSummary?: ImportSummaryResponse | null;
  loading?: boolean;
  /** Workflow perspective selection callback. */
  onSelectWorkflowGroup?: (category: string, groupKey: string, groupLabel: string) => void;
  /** Currently active workflow perspective. */
  activeWorkflowPerspective?: { category: string; groupKey: string; groupLabel: string } | null;
  /** Current item ID in the story panel (for contextual notes). */
  currentItemId?: string | null;
  /** Current user name (for note authorship). */
  userName?: string;
  /** Navigation handler for instance-level clicks in the tree. */
  onNavigate?: (itemId: string) => void;
  /** Whether Quiet mode is active. DTC-7. */
  isQuiet?: boolean;
  /** Callback when Quiet mode is toggled. DTC-7. */
  onQuietToggle?: () => void;
}

export function ExecSummaryDock({
  isOpen,
  categories,
  importSummary,
  loading,
  onSelectWorkflowGroup,
  activeWorkflowPerspective,
  currentItemId,
  userName = "",
  onNavigate,
  isQuiet = false,
  onQuietToggle,
}: ExecSummaryDockProps) {
  const { notes, addNote } = useNotes(currentItemId ?? null);
  return (
    <div
      className="shrink-0 bg-vellum border-l border-rule transition-[width] duration-200 ease-in-out overflow-hidden"
      style={{ width: isOpen ? 320 : 0 }}
    >
      <div
        className={`w-[320px] h-full flex flex-col overflow-y-auto overflow-x-hidden transition-opacity duration-150 ${
          isOpen ? "opacity-100 delay-75" : "opacity-0"
        }`}
      >
        {/* Dock header with Quiet toggle (DTC-7) */}
        <div className="px-3 py-2 border-b border-rule shrink-0 flex flex-col gap-1.5">
          {onQuietToggle && (
            <QuietButton isActive={isQuiet} onToggle={onQuietToggle} />
          )}
          <span className="text-xs font-mono uppercase tracking-wide text-trace">
            Exec Summary
          </span>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="px-3 py-4 text-xs text-trace animate-pulse">
            Loading project health…
          </div>
        )}

        {/* Category tree */}
        {!loading && categories.length > 0 && (
          <div className="flex-1 py-1">
            {categories.map((category) => (
              <DockCategoryRow
                key={category.key}
                category={category}
                isExpanded={
                  activeWorkflowPerspective?.category === category.key
                }
              >
                {category.groups.map((group) => (
                  <DockTypeRow
                    key={group.key}
                    group={group}
                    colorClass={category.colorClass}
                    isSelected={
                      activeWorkflowPerspective?.category === category.key &&
                      activeWorkflowPerspective?.groupKey === group.key
                    }
                    onClick={
                      onSelectWorkflowGroup
                        ? () =>
                            onSelectWorkflowGroup(
                              category.key,
                              group.key,
                              group.label
                            )
                        : undefined
                    }
                    onNavigate={onNavigate}
                  />
                ))}
              </DockCategoryRow>
            ))}
          </div>
        )}

        {/* Empty state (no data and not loading) */}
        {!loading && categories.length === 0 && (
          <div className="px-3 py-4 text-xs text-trace">
            No project health data available.
          </div>
        )}

        {/* Import summary bar */}
        {!loading && <DockImportBar importSummary={importSummary ?? null} />}

        {/* Notes area (bottom zone) — contextual to current item */}
        <NotesArea
          notes={notes.map((n) => ({
            id: n.id,
            content: n.content,
            author: n.author,
            date: n.created_at ? new Date(n.created_at).toLocaleDateString() : undefined,
          }))}
          hasCurrentItem={!!currentItemId}
          onAddNote={(content) => addNote(content, userName)}
        />
      </div>
    </div>
  );
}
