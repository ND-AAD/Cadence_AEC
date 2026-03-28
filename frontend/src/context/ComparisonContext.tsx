// ─── Temporal Context ────────────────────────────────────────────
// Global temporal state: manages comparison mode, value modes
// (submitted/cumulative), and Quiet mode.
//
// DTC-1: Refactored from T-6 tray model. Replaces isCurrent with isQuiet,
// viewMode with isComparing, removes hasExplicitlyToggled. Default value
// mode changed to submitted per DS-2 Addendum v3 §4.2.
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

export type ValueMode = "submitted" | "cumulative";

interface ContextInfo {
  id: string;
  identifier: string | null;
}

export interface TemporalState {
  // ── Comparison fields (preserved from ComparisonContext) ──
  /** True when comparison mode is active (data loaded, two-column layout). */
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

  // ── Temporal control fields (DTC-1, replaces T-6 tray model) ──
  /** True when comparison mode is engaged. Single is implicit (isComparing=false). */
  isComparing: boolean;
  /** Value mode: submitted or cumulative. Persists across navigation. */
  valueMode: ValueMode;
  /** True when Quiet mode is active (replaces isCurrent). */
  isQuiet: boolean;

  // ── State preservation for returning from Quiet ──
  /** Preserved milestone before entering Quiet. */
  preservedMilestone: ContextInfo | null;
  /** Preserved valueMode before entering Quiet. */
  preservedValueMode: ValueMode;
}

/** Default temporal state. Submitted, not Quiet, not comparing. */
const initialState: TemporalState = {
  isActive: false,
  fromContext: null,
  toContext: null,
  dataCache: {},
  pending: false,
  error: null,
  isComparing: false,
  valueMode: "submitted",
  isQuiet: false,
  preservedMilestone: null,
  preservedValueMode: "submitted",
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
  // Temporal control actions (DTC-1)
  | { type: "SET_COMPARING"; isComparing: boolean }
  | { type: "SET_VALUE_MODE"; valueMode: ValueMode }
  | { type: "ENTER_QUIET" }
  | { type: "EXIT_QUIET" }
  | { type: "SET_MILESTONE"; milestone: ContextInfo | null };

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
      // Only reset comparison-specific fields. Preserve temporal controls
      // (isQuiet, valueMode, isComparing, preserved state) so deactivation
      // doesn't clobber the user's current mode.
      return {
        ...state,
        isActive: false,
        fromContext: null,
        toContext: null,
        dataCache: {},
        pending: false,
        error: null,
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

    case "SET_COMPARING":
      return { ...state, isComparing: action.isComparing };

    case "SET_VALUE_MODE":
      return { ...state, valueMode: action.valueMode };

    case "ENTER_QUIET":
      return {
        ...state,
        isQuiet: true,
        preservedMilestone: state.fromContext,
        preservedValueMode: state.valueMode,
      };

    case "EXIT_QUIET":
      return {
        ...state,
        isQuiet: false,
        valueMode: state.preservedValueMode,
        fromContext: state.preservedMilestone,
      };

    case "SET_MILESTONE":
      return { ...state, fromContext: action.milestone };

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

  // ── Temporal control actions (DTC-1) ──
  /** Set comparing state. True opens comparison; false returns to single. */
  setComparing: (isComparing: boolean) => void;
  /** Set value mode (submitted or cumulative). Persistent across navigation. */
  setValueMode: (valueMode: ValueMode) => void;
  /** Preserve current state and enter Quiet mode. */
  enterQuiet: () => void;
  /** Exit Quiet mode and restore preserved state. */
  exitQuiet: () => void;
  /** Set the active milestone context (for milestone chip selection). */
  setMilestone: (milestone: ContextInfo | null) => void;
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
  const setComparing = useCallback((isComparing: boolean) => {
    dispatch({ type: "SET_COMPARING", isComparing });
  }, []);

  const setValueMode = useCallback((valueMode: ValueMode) => {
    dispatch({ type: "SET_VALUE_MODE", valueMode });
  }, []);

  const enterQuiet = useCallback(() => {
    dispatch({ type: "ENTER_QUIET" });
  }, []);

  const exitQuiet = useCallback(() => {
    dispatch({ type: "EXIT_QUIET" });
  }, []);

  const setMilestone = useCallback(
    (milestone: ContextInfo | null) => {
      dispatch({ type: "SET_MILESTONE", milestone });
    },
    [],
  );

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
    setComparing,
    setValueMode,
    enterQuiet,
    exitQuiet,
    setMilestone,
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
