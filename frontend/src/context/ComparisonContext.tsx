// ─── Temporal Context ────────────────────────────────────────────
// Global temporal state: manages view modes (single/compare), value modes
// (submitted/cumulative), and Current mode.
//
// T-6: Evolved from ComparisonContext. Adds temporal control fields
// (viewMode, valueMode, isCurrent, hasExplicitlyToggled) and semantics
// for automatic value mode switching per DS-2 Addendum §4.2.
//
// Comparison activation/deactivation preserved; comparison-related actions
// still live here for backward compatibility.
//
// Peer to NavigationContext (not nested).

import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  type ReactNode,
} from "react";
import type { ItemComparison } from "@/api/comparison";

// ─── Types ───────────────────────────────────────────────────────

export type ViewMode = "single" | "compare";
export type ValueMode = "submitted" | "cumulative";

interface ContextInfo {
  id: string;
  identifier: string | null;
}

export interface TemporalState {
  // ── Comparison fields (preserved from ComparisonContext) ──
  /** True when comparison mode is active. */
  isActive: boolean;
  /** The "from" (earlier) milestone context. */
  fromContext: ContextInfo | null;
  /** The "to" (later) milestone context. */
  toContext: ContextInfo | null;
  /** Cached per-item comparison data (keyed by item ID). */
  dataCache: Record<string, ItemComparison>;
  /** True while a comparison API call is in flight. */
  pending: boolean;
  /** Error from the last failed comparison request. */
  error: string | null;

  // ── Temporal control fields (new for T-6) ──
  /** View mode: single or compare. */
  viewMode: ViewMode;
  /** Value mode: submitted or cumulative. */
  valueMode: ValueMode;
  /** True when user has selected Current mode. */
  isCurrent: boolean;
  /** True if user has explicitly toggled valueMode (not auto-switched). */
  hasExplicitlyToggled: boolean;

  // ── State preservation for returning from Current ──
  /** Preserved viewMode before entering Current. */
  preservedViewMode: ViewMode;
  /** Preserved valueMode before entering Current. */
  preservedValueMode: ValueMode;
  /** Preserved context (for single view) before entering Current. */
  preservedContext: ContextInfo | null;
}

/** Default temporal state. Single + Cumulative, not Current, not explicitly toggled. */
const initialState: TemporalState = {
  isActive: false,
  fromContext: null,
  toContext: null,
  dataCache: {},
  pending: false,
  error: null,
  viewMode: "single",
  valueMode: "cumulative",
  isCurrent: false,
  hasExplicitlyToggled: false,
  preservedViewMode: "single",
  preservedValueMode: "cumulative",
  preservedContext: null,
};

// ─── Actions ─────────────────────────────────────────────────────

type TemporalAction =
  // Comparison actions (preserved)
  | { type: "ACTIVATE"; fromContext: ContextInfo; toContext: ContextInfo }
  | { type: "DEACTIVATE" }
  | { type: "SWAP_CONTEXTS" }
  | { type: "SET_ITEM_DATA"; itemId: string; data: ItemComparison }
  | { type: "SET_BATCH_DATA"; items: ItemComparison[] }
  | { type: "SET_PENDING"; pending: boolean }
  | { type: "SET_ERROR"; error: string | null }
  | { type: "CLEAR_CACHE" }
  // Temporal control actions (new for T-6)
  | { type: "SET_VIEW_MODE"; viewMode: ViewMode }
  | { type: "SET_VALUE_MODE"; valueMode: ValueMode }
  | { type: "ENTER_CURRENT" }
  | { type: "EXIT_CURRENT" };

function temporalReducer(
  state: TemporalState,
  action: TemporalAction,
): TemporalState {
  switch (action.type) {
    case "ACTIVATE":
      return {
        ...state,
        isActive: true,
        fromContext: action.fromContext,
        toContext: action.toContext,
        dataCache: {},
        pending: false,
        error: null,
      };

    case "DEACTIVATE":
      return {
        ...initialState,
      };

    case "SWAP_CONTEXTS":
      return {
        ...state,
        fromContext: state.toContext,
        toContext: state.fromContext,
        dataCache: {},
      };

    case "SET_ITEM_DATA":
      return {
        ...state,
        dataCache: {
          ...state.dataCache,
          [action.itemId]: action.data,
        },
      };

    case "SET_BATCH_DATA": {
      const newCache = { ...state.dataCache };
      for (const item of action.items) {
        newCache[item.item_id] = item;
      }
      return { ...state, dataCache: newCache };
    }

    case "SET_PENDING":
      return { ...state, pending: action.pending };

    case "SET_ERROR":
      return { ...state, error: action.error, pending: false };

    case "CLEAR_CACHE":
      return { ...state, dataCache: {} };

    case "SET_VIEW_MODE": {
      // When switching view modes, auto-switch value mode unless explicitly toggled.
      let nextValueMode = state.valueMode;
      if (!state.hasExplicitlyToggled) {
        // Auto-switch: compare → submitted, single → cumulative
        nextValueMode = action.viewMode === "compare" ? "submitted" : "cumulative";
      }
      return {
        ...state,
        viewMode: action.viewMode,
        valueMode: nextValueMode,
      };
    }

    case "SET_VALUE_MODE":
      return {
        ...state,
        valueMode: action.valueMode,
        hasExplicitlyToggled: true,
      };

    case "ENTER_CURRENT":
      return {
        ...state,
        isCurrent: true,
        preservedViewMode: state.viewMode,
        preservedValueMode: state.valueMode,
        preservedContext: state.fromContext,
      };

    case "EXIT_CURRENT":
      return {
        ...state,
        isCurrent: false,
        viewMode: state.preservedViewMode,
        valueMode: state.preservedValueMode,
        fromContext: state.preservedContext,
      };

    default:
      return state;
  }
}

// ─── Context ─────────────────────────────────────────────────────

interface TemporalContextValue {
  state: TemporalState;

  // ── Comparison actions (preserved for backward compatibility) ──
  /** Activate comparison between two milestone contexts. */
  activate: (fromContext: ContextInfo, toContext: ContextInfo) => void;
  /** Deactivate comparison mode and clear all data. */
  deactivate: () => void;
  /** Swap from/to contexts. */
  swapContexts: () => void;
  /** Cache comparison data for a single item. */
  setItemData: (itemId: string, data: ItemComparison) => void;
  /** Cache comparison data for a batch of items. */
  setBatchData: (items: ItemComparison[]) => void;
  /** Set loading state. */
  setPending: (pending: boolean) => void;
  /** Set error state. */
  setError: (error: string | null) => void;
  /** Get cached comparison data for an item. */
  getItemComparison: (itemId: string) => ItemComparison | undefined;

  // ── Temporal control actions (new for T-6) ──
  /** Set view mode (single or compare). Auto-switches value mode if not explicitly toggled. */
  setViewMode: (viewMode: ViewMode) => void;
  /** Set value mode (submitted or cumulative). Marks user choice as explicit. */
  setValueMode: (valueMode: ValueMode) => void;
  /** Preserve current state and enter Current mode. */
  enterCurrent: () => void;
  /** Exit Current mode and restore preserved state. */
  exitCurrent: () => void;
}

const TemporalCtx = createContext<TemporalContextValue | null>(null);

// ─── Provider ────────────────────────────────────────────────────

export function TemporalProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(temporalReducer, initialState);

  // Comparison actions
  const activate = useCallback(
    (fromContext: ContextInfo, toContext: ContextInfo) => {
      dispatch({ type: "ACTIVATE", fromContext, toContext });
    },
    [],
  );

  const deactivate = useCallback(() => {
    dispatch({ type: "DEACTIVATE" });
  }, []);

  const swapContexts = useCallback(() => {
    dispatch({ type: "SWAP_CONTEXTS" });
  }, []);

  const setItemData = useCallback(
    (itemId: string, data: ItemComparison) => {
      dispatch({ type: "SET_ITEM_DATA", itemId, data });
    },
    [],
  );

  const setBatchData = useCallback((items: ItemComparison[]) => {
    dispatch({ type: "SET_BATCH_DATA", items });
  }, []);

  const setPending = useCallback((pending: boolean) => {
    dispatch({ type: "SET_PENDING", pending });
  }, []);

  const setError = useCallback((error: string | null) => {
    dispatch({ type: "SET_ERROR", error });
  }, []);

  const getItemComparison = useCallback(
    (itemId: string) => state.dataCache[itemId],
    [state.dataCache],
  );

  // Temporal control actions
  const setViewMode = useCallback((viewMode: ViewMode) => {
    dispatch({ type: "SET_VIEW_MODE", viewMode });
  }, []);

  const setValueMode = useCallback((valueMode: ValueMode) => {
    dispatch({ type: "SET_VALUE_MODE", valueMode });
  }, []);

  const enterCurrent = useCallback(() => {
    dispatch({ type: "ENTER_CURRENT" });
  }, []);

  const exitCurrent = useCallback(() => {
    dispatch({ type: "EXIT_CURRENT" });
  }, []);

  const value: TemporalContextValue = {
    state,
    activate,
    deactivate,
    swapContexts,
    setItemData,
    setBatchData,
    setPending,
    setError,
    getItemComparison,
    setViewMode,
    setValueMode,
    enterCurrent,
    exitCurrent,
  };

  return (
    <TemporalCtx.Provider value={value}>{children}</TemporalCtx.Provider>
  );
}

// ─── Hooks ───────────────────────────────────────────────────────

/**
 * Use the temporal context. Returns state and all action dispatchers.
 */
export function useTemporalContext(): TemporalContextValue {
  const ctx = useContext(TemporalCtx);
  if (!ctx) {
    throw new Error(
      "useTemporalContext must be used within a TemporalProvider",
    );
  }
  return ctx;
}

/**
 * Legacy alias for backward compatibility. New code should use useTemporalContext.
 */
export function useComparisonContext(): TemporalContextValue {
  return useTemporalContext();
}

/**
 * Legacy alias for backward compatibility. New code should use TemporalProvider.
 */
export function ComparisonProvider({ children }: { children: ReactNode }) {
  return <TemporalProvider>{children}</TemporalProvider>;
}
