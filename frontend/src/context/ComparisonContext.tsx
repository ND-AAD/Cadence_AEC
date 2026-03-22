// ─── Comparison Context ───────────────────────────────────────────
// Global comparison state: manages activation, context pair, and
// per-item comparison data caching.
//
// DS-2: Comparison is a persistent lens — stays active through all
// navigation (drill-in, lateral, ascent). Deactivated only explicitly.
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

// ─── State ───────────────────────────────────────────────────────

interface ContextInfo {
  id: string;
  identifier: string | null;
}

export interface ComparisonState {
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
}

const initialState: ComparisonState = {
  isActive: false,
  fromContext: null,
  toContext: null,
  dataCache: {},
  pending: false,
  error: null,
};

// ─── Actions ─────────────────────────────────────────────────────

type ComparisonAction =
  | { type: "ACTIVATE"; fromContext: ContextInfo; toContext: ContextInfo }
  | { type: "DEACTIVATE" }
  | { type: "SWAP_CONTEXTS" }
  | { type: "SET_ITEM_DATA"; itemId: string; data: ItemComparison }
  | { type: "SET_BATCH_DATA"; items: ItemComparison[] }
  | { type: "SET_PENDING"; pending: boolean }
  | { type: "SET_ERROR"; error: string | null }
  | { type: "CLEAR_CACHE" };

function comparisonReducer(
  state: ComparisonState,
  action: ComparisonAction,
): ComparisonState {
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

    default:
      return state;
  }
}

// ─── Context ─────────────────────────────────────────────────────

interface ComparisonContextValue {
  state: ComparisonState;
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
}

const ComparisonCtx = createContext<ComparisonContextValue | null>(null);

// ─── Provider ────────────────────────────────────────────────────

export function ComparisonProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(comparisonReducer, initialState);

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

  const value: ComparisonContextValue = {
    state,
    activate,
    deactivate,
    swapContexts,
    setItemData,
    setBatchData,
    setPending,
    setError,
    getItemComparison,
  };

  return (
    <ComparisonCtx.Provider value={value}>{children}</ComparisonCtx.Provider>
  );
}

// ─── Hook ────────────────────────────────────────────────────────

export function useComparisonContext(): ComparisonContextValue {
  const ctx = useContext(ComparisonCtx);
  if (!ctx) {
    throw new Error(
      "useComparisonContext must be used within a ComparisonProvider",
    );
  }
  return ctx;
}
