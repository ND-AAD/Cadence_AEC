// ─── Story Panel ──────────────────────────────────────────────────
// Center panel: main content area. Type-driven rendering of selected item.
// DS-1 §2.2: Fills remaining width. Expands when side panels close.
// DS-1 §5: Content determined by selected item's type.
// DS-2 §2: Overlay wash when comparison mode is active.

import type { ReactNode } from "react";

interface StoryPanelProps {
  children?: ReactNode;
  /** When true, apply overlay wash (comparison mode active). */
  comparisonActive?: boolean;
}

export function StoryPanel({ children, comparisonActive = false }: StoryPanelProps) {
  return (
    <div
      className={`flex-1 min-w-0 overflow-y-auto transition-all duration-200 ${
        comparisonActive
          ? "bg-overlay-wash border-2 border-overlay-border"
          : "bg-sheet"
      }`}
    >
      {children ?? (
        <div className="flex items-center justify-center h-full text-sm text-trace">
          <p>Select an item to view its story.</p>
        </div>
      )}
    </div>
  );
}
