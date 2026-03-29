// ─── usePanelState Hook ───────────────────────────────────────────
// Manages the open/closed state of the three-panel layout's side panels.
// Scale panel (left): default open.
// Exec summary dock (right): default collapsed.

import { useState, useCallback } from "react";

export interface PanelState {
  scalePanelOpen: boolean;
  dockOpen: boolean;
  toggleScalePanel: () => void;
  toggleDock: () => void;
}

export function usePanelState(): PanelState {
  const [scalePanelOpen, setScalePanelOpen] = useState(true);
  const [dockOpen, setDockOpen] = useState(false);

  const toggleScalePanel = useCallback(
    () => setScalePanelOpen((prev) => !prev),
    [],
  );

  const toggleDock = useCallback(
    () => setDockOpen((prev) => !prev),
    [],
  );

  return {
    scalePanelOpen,
    dockOpen,
    toggleScalePanel,
    toggleDock,
  };
}
