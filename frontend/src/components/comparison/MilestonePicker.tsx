// ─── Milestone Picker ─────────────────────────────────────────────
// Dropdown for selecting from/to milestones to activate comparison.
// DS-2 §2: User picks two milestone contexts, then clicks "Compare".
//
// Lists available milestones from connected items of the project root.
// Styled as overlay-spectrum dropdown (paper-and-ink metaphor).

import { useState, useEffect, useRef } from "react";

export interface MilestoneOption {
  id: string;
  label: string;
}

interface MilestonePickerProps {
  /** Available milestones to choose from. */
  milestones: MilestoneOption[];
  /** Called when user confirms selection. */
  onCompare: (fromId: string, toId: string) => void;
  /** Called when user closes the picker without comparing. */
  onClose: () => void;
}

export function MilestonePicker({
  milestones,
  onCompare,
  onClose,
}: MilestonePickerProps) {
  // Default: auto-select second-to-last and last milestones.
  const [fromId, setFromId] = useState<string>(
    milestones.length >= 2 ? milestones[milestones.length - 2].id : "",
  );
  const [toId, setToId] = useState<string>(
    milestones.length >= 1 ? milestones[milestones.length - 1].id : "",
  );

  const panelRef = useRef<HTMLDivElement>(null);

  // Close on outside click.
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  // Close on Escape.
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const canCompare = fromId && toId && fromId !== toId;

  return (
    <div
      ref={panelRef}
      className="absolute top-full right-0 mt-1 z-50 bg-sheet border border-overlay-border rounded shadow-sm w-64 p-3 space-y-3"
    >
      <div className="text-xs font-mono uppercase text-overlay-border">
        Compare Milestones
      </div>

      {/* From selector */}
      <label className="block space-y-1">
        <span className="text-xs text-graphite">From (earlier)</span>
        <select
          value={fromId}
          onChange={(e) => setFromId(e.target.value)}
          className="w-full text-sm border border-rule rounded px-2 py-1 bg-sheet text-ink focus:outline-2 focus:outline-overlay"
        >
          <option value="">Select…</option>
          {milestones.map((m) => (
            <option key={m.id} value={m.id} disabled={m.id === toId}>
              {m.label}
            </option>
          ))}
        </select>
      </label>

      {/* To selector */}
      <label className="block space-y-1">
        <span className="text-xs text-graphite">To (later)</span>
        <select
          value={toId}
          onChange={(e) => setToId(e.target.value)}
          className="w-full text-sm border border-rule rounded px-2 py-1 bg-sheet text-ink focus:outline-2 focus:outline-overlay"
        >
          <option value="">Select…</option>
          {milestones.map((m) => (
            <option key={m.id} value={m.id} disabled={m.id === fromId}>
              {m.label}
            </option>
          ))}
        </select>
      </label>

      {/* Actions */}
      <div className="flex items-center justify-between pt-1">
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-graphite hover:text-ink transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => canCompare && onCompare(fromId, toId)}
          disabled={!canCompare}
          className={`text-xs px-3 py-1 rounded border transition-colors ${
            canCompare
              ? "bg-overlay-wash text-overlay border-overlay hover:bg-overlay/10"
              : "bg-board/30 text-trace border-rule cursor-not-allowed"
          }`}
        >
          Compare
        </button>
      </div>
    </div>
  );
}
