// ─── Layout Frame ─────────────────────────────────────────────────
// Three-panel application shell per DS-1 §2.
//
// ┌──────────────────────────────────────────────────────────────┐
// │ BREADCRUMB BAR                                               │
// ├────────┬──┬────────────────────────────────┬──┬──────────────┤
// │ SCALE  │◀ │        STORY PANEL             │▶ │  EXEC        │
// │ PANEL  │  │        (main area)             │  │  SUMMARY     │
// │ (0/280)│  │  ← grows when panels close →   │  │  DOCK (0/320)│
// └────────┴──┴────────────────────────────────┴──┴──────────────┘
//
// Toggle buttons live BETWEEN panels and story — always in the same
// position regardless of panel state.

import { useMemo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { usePanelState } from "@/hooks/usePanelState";
import { Breadcrumb } from "@/components/breadcrumb/Breadcrumb";
import { ScalePanel } from "./ScalePanel";
import { StoryPanel } from "./StoryPanel";
import { KernelButton } from "./KernelButton";
import { ValueModeToggle } from "./ValueModeToggle";
import { ExecSummaryDock } from "@/components/dock/ExecSummaryDock";
import { SearchTrigger } from "@/components/search/SearchTrigger";
import type { DockCategory, ImportSummaryResponse } from "@/types/dashboard";

interface LayoutFrameProps {
  /** Content rendered in the story panel (center). */
  children?: ReactNode;
  /** Content rendered in the scale panel (left). */
  scaleContent?: ReactNode;
  /** Dock category tree for the exec summary panel. */
  dockCategories?: DockCategory[];
  /** Last import summary for the dock footer. */
  importSummary?: ImportSummaryResponse | null;
  /** Whether dock data is still loading. */
  dockLoading?: boolean;
  /** Workflow perspective selection callback (type-level). */
  onSelectWorkflowGroup?: (category: string, groupKey: string, groupLabel: string) => void;
  /** Category-level workflow perspective selection callback. */
  onSelectWorkflowCategory?: (category: string) => void;
  /** Currently active workflow perspective. */
  activeWorkflowPerspective?: { category: string; groupKey: string; groupLabel: string } | null;
  /** Whether comparison mode is active (DS-2). */
  comparisonActive?: boolean;
  /** Comparison badge content for breadcrumb bar. */
  comparisonBadge?: ReactNode;
  /** Current value mode (submitted or cumulative). DTC-6. */
  valueMode?: "submitted" | "cumulative";
  /** Callback when value mode changes. DTC-6. */
  onValueModeChange?: (mode: "submitted" | "cumulative") => void;
  /** Whether Quiet mode is active (disables value mode toggle, suppresses kernel count). DTC-6. */
  isQuiet?: boolean;
  /** Callback when Quiet mode is toggled (passed to ExecSummaryDock). DTC-7. */
  onQuietToggle?: () => void;
  /** Whether we're inside a project (show Add Data button). */
  inProject?: boolean;
  /** Whether the project has data (controls Add Data button styling per A6). */
  hasData?: boolean;
  /** Callback to open the Add Data modal. */
  onAddData?: () => void;
  /** Callback to open the search modal (OB-8). */
  onSearchOpen?: () => void;
  /** Callback when dock navigation occurs. */
  onDockNavigate?: (itemId: string) => void;
}

export function LayoutFrame({
  children,
  scaleContent,
  dockCategories,
  importSummary,
  dockLoading,
  onSelectWorkflowGroup,
  onSelectWorkflowCategory,
  activeWorkflowPerspective,
  comparisonActive = false,
  comparisonBadge,
  valueMode = "submitted",
  onValueModeChange,
  isQuiet = false,
  onQuietToggle,
  inProject = false,
  hasData = false,
  onAddData,
  onSearchOpen,
  onDockNavigate,
}: LayoutFrameProps) {
  const { scalePanelOpen, dockOpen, toggleScalePanel, toggleDock } =
    usePanelState();

  // Total action items for the dock kernel badge.
  const dockActionCount = useMemo(() => {
    if (!dockCategories) return 0;
    return dockCategories.reduce(
      (sum, cat) => (cat.key !== "notes" ? sum + cat.count : sum),
      0,
    );
  }, [dockCategories]);

  return (
    <div className="h-screen flex flex-col bg-vellum overflow-hidden">
      {/* ─── Breadcrumb Bar ─────────────────────────────────── */}
      <div className="px-4 py-2 bg-vellum border-b border-rule shrink-0 flex items-center gap-3">
        {/* Cadence wordmark — persistent brand element, always returns to project list */}
        <Link
          to="/projects"
          className="text-lg font-semibold tracking-tight text-ink shrink-0 select-none hover:text-ink/80 transition-colors"
        >
          Cadence
        </Link>
        <span className="w-px h-4 bg-rule shrink-0" />
        <Breadcrumb />
        {/* Right-aligned action area */}
        <span className="flex-1" />

        {/* Search trigger (OB-8) */}
        {onSearchOpen && <SearchTrigger onFocus={onSearchOpen} />}

        {/* Add Data button — A6: primary when empty, quiet when has data */}
        {inProject && onAddData && (
          <button
            onClick={onAddData}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              hasData
                ? "text-graphite border border-rule hover:text-ink hover:border-ink"
                : "bg-ink text-sheet hover:bg-ink/90"
            }`}
          >
            + Add Data
          </button>
        )}

        {/* Value mode toggle — persistent, disabled in Quiet (DTC-6) */}
        {onValueModeChange && (
          <ValueModeToggle
            value={valueMode}
            onChange={onValueModeChange}
            disabled={isQuiet}
          />
        )}

        {/* Comparison badge (shown when comparison active) */}
        {comparisonBadge}
      </div>

      {/* ─── Three-Panel Content Area ──────────────────────── */}
      <div className="flex flex-1 min-h-0">
        {/* Scale panel (left) */}
        <ScalePanel isOpen={scalePanelOpen}>
          {scaleContent}
        </ScalePanel>

        {/* Left toggle — always at left edge of story panel */}
        <div className="shrink-0 flex flex-col border-r border-rule bg-vellum">
          <KernelButton
            direction="left"
            isOpen={scalePanelOpen}
            onToggle={toggleScalePanel}
            label={scalePanelOpen ? "Collapse scale panel" : "Expand scale panel"}
          />
        </div>

        {/* Story panel (center) */}
        <StoryPanel comparisonActive={comparisonActive}>{children}</StoryPanel>

        {/* Right toggle — always at right edge of story panel */}
        <div className="shrink-0 flex flex-col border-l border-rule bg-vellum">
          <KernelButton
            direction="right"
            isOpen={dockOpen}
            onToggle={toggleDock}
            label={dockOpen ? "Collapse exec summary" : "Expand exec summary"}
            count={isQuiet ? undefined : dockActionCount > 0 ? dockActionCount : undefined}
          />
        </div>

        {/* Exec summary dock (right) */}
        <ExecSummaryDock
          isOpen={dockOpen}
          categories={dockCategories ?? []}
          importSummary={importSummary}
          loading={dockLoading}
          onSelectWorkflowGroup={onSelectWorkflowGroup}
          onSelectWorkflowCategory={onSelectWorkflowCategory}
          activeWorkflowPerspective={activeWorkflowPerspective}
          onNavigate={onDockNavigate}
          isQuiet={isQuiet}
          onQuietToggle={onQuietToggle}
        />
      </div>
    </div>
  );
}
