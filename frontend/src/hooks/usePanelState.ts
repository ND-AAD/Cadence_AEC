// ─── usePanelState Hook ───────────────────────────────────────────
// Manages the open/closed state of the three-panel layout's side panels.
// Scale panel (left): default open.
// Notes panel (right): default collapsed.

import { useState, useCallback } from "react";

export interface PanelState {
  scalePanelOpen: boolean;
  notesPanelOpen: boolean;
  toggleScalePanel: () => void;
  toggleNotesPanel: () => void;
}

export function usePanelState(): PanelState {
  const [scalePanelOpen, setScalePanelOpen] = useState(true);
  const [notesPanelOpen, setNotesPanelOpen] = useState(false);

  const toggleScalePanel = useCallback(
    () => setScalePanelOpen((prev) => !prev),
    [],
  );

  const toggleNotesPanel = useCallback(
    () => setNotesPanelOpen((prev) => !prev),
    [],
  );

  return {
    scalePanelOpen,
    notesPanelOpen,
    toggleScalePanel,
    toggleNotesPanel,
  };
}
