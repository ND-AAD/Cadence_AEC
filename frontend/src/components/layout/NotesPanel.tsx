// ─── Notes / Reconciliation Panel ─────────────────────────────────
// Right side panel: notes, reconciliation actions, @-mentions.
// DS-1 §2.2: Default collapsed to kernel icon. Opens to panel width.
// DS-1 §8: Notes panel — kernel shows note count.

import type { ReactNode } from "react";
import { KernelButton } from "./KernelButton";

interface NotesPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  /** Note count to display on the kernel icon. */
  noteCount?: number;
  children?: ReactNode;
}

export function NotesPanel({
  isOpen,
  onToggle,
  noteCount,
  children,
}: NotesPanelProps) {
  return (
    <div
      className="flex shrink-0 bg-vellum border-l border-rule transition-[width] duration-200 ease-in-out overflow-hidden"
      style={{ width: isOpen ? 320 : 48 }}
    >
      {/* Scrollable content area — fades in/out with panel open/close */}
      <div
        className={`flex-1 min-w-0 overflow-y-auto overflow-x-hidden transition-opacity duration-150 ${
          isOpen ? "opacity-100 delay-75" : "opacity-0"
        }`}
      >
        {children ?? (
          <div className="p-4 text-sm text-trace">
            <p className="text-xs font-mono uppercase tracking-wide">
              Notes
            </p>
            <p className="mt-2 text-xs text-trace/70">
              Notes and reconciliation actions will appear here.
            </p>
          </div>
        )}
      </div>

      {/* Kernel button — always visible, on the left edge of the right panel */}
      <div className="flex flex-col items-center border-l border-rule/50 shrink-0">
        <KernelButton
          direction="right"
          isOpen={isOpen}
          onToggle={onToggle}
          label={isOpen ? "Collapse notes panel" : "Expand notes panel"}
          count={noteCount}
        />
      </div>
    </div>
  );
}
