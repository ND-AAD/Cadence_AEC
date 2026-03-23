// ─── Navigation Context ───────────────────────────────────────────
// Global breadcrumb state management via React Context + useReducer.
//
// The reducer handles:
//   - Linear breadcrumb (push, pop, set)
//   - Fork creation (Z-axis lateral jumps)
//   - Fork absorption (navigate to item on dead branch → fork resolves)
//   - Pending/error states during async navigation
//
// Browser history integration:
//   Every breadcrumb change pushes to window.history so the browser
//   back/forward buttons mirror the Powers of Ten navigation. Pressing
//   back pops one breadcrumb level. Pressing back at the project root
//   returns to /projects (the React Router entry).

import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";

import type {
  BreadcrumbItem,
  NavigationState,
  NavigationAction,
} from "@/types/navigation";
import { navigateToItem } from "@/api/navigation";
import { getItems, itemDisplayName } from "@/api/items";
import { formatWorkflowBreadcrumb } from "@/utils/workflowBreadcrumb";

// ─── Initial State ────────────────────────────────────────────────

const initialState: NavigationState = {
  breadcrumb: [],
  fork: null,
  pending: false,
  error: null,
  lastAction: null,
};

// ─── Reducer ──────────────────────────────────────────────────────

function navigationReducer(
  state: NavigationState,
  action: NavigationAction,
): NavigationState {
  switch (action.type) {
    case "NAVIGATE_START":
      return { ...state, pending: true, error: null };

    case "NAVIGATE_SUCCESS": {
      if (action.action === "no_path") {
        return {
          ...state,
          pending: false,
          error: "No connection path found.",
          lastAction: "no_path",
        };
      }

      // If we had a fork, any successful navigation resolves it.
      if (state.fork) {
        return {
          ...state,
          breadcrumb: action.breadcrumb,
          fork: null,
          pending: false,
          error: null,
          lastAction: action.action,
        };
      }

      return {
        ...state,
        breadcrumb: action.breadcrumb,
        pending: false,
        error: null,
        lastAction: action.action,
      };
    }

    case "NAVIGATE_ERROR":
      return { ...state, pending: false, error: action.error };

    case "SET_BREADCRUMB":
      return {
        ...state,
        breadcrumb: action.breadcrumb,
        fork: null,
        error: null,
        lastAction: null,
      };

    case "POP_TO": {
      const newBreadcrumb = state.breadcrumb.slice(0, action.index + 1);
      return {
        ...state,
        breadcrumb: newBreadcrumb,
        fork: null,
        error: null,
        lastAction: "bounce_back",
      };
    }

    case "FORK_CREATE":
      return {
        ...state,
        fork: {
          stem: action.stem,
          active: action.active,
          inactive: action.inactive,
        },
        pending: false,
        error: null,
        lastAction: "bounce_back",
      };

    case "FORK_ABSORB":
      return {
        ...state,
        breadcrumb: action.breadcrumb,
        fork: null,
        pending: false,
        error: null,
        lastAction: "push",
      };

    default:
      return state;
  }
}

// ─── Browser History Helpers ──────────────────────────────────────

/** Key used in history.state to identify Cadence breadcrumb entries. */
const HISTORY_KEY = "cadenceBreadcrumb";

function getEffectiveBreadcrumb(state: NavigationState): BreadcrumbItem[] {
  if (state.fork) {
    return [...state.fork.stem, ...state.fork.active];
  }
  return state.breadcrumb;
}

// ─── Context ──────────────────────────────────────────────────────

interface NavigationContextValue {
  state: NavigationState;
  /** Navigate to a target item. Handles the full async flow. */
  navigate: (targetId: string) => Promise<void>;
  /** Snap back to a breadcrumb segment by index. */
  popTo: (index: number) => void;
  /** Directly set the breadcrumb (for initial load / seed). */
  setBreadcrumb: (items: BreadcrumbItem[]) => void;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(navigationReducer, initialState);

  // ── History sync refs ───────────────────────────────────────────
  // isRestoringRef: true when a popstate event is driving the breadcrumb
  // change. Prevents the sync effect from pushing a duplicate entry.
  // shouldReplaceRef: true when setBreadcrumb is called (initial load).
  // The next sync should replaceState instead of pushState.
  const isRestoringRef = useRef(false);
  const shouldReplaceRef = useRef(false);

  // ── Sync breadcrumb → browser history ───────────────────────────
  // Runs after every render where breadcrumb or fork changed.
  useEffect(() => {
    // Skip if this change came from a popstate restoration.
    if (isRestoringRef.current) {
      isRestoringRef.current = false;
      return;
    }

    const effectiveBc = getEffectiveBreadcrumb(state);
    if (effectiveBc.length === 0) return;

    if (shouldReplaceRef.current) {
      // Initial load / seed: replace current entry, don't add new one.
      // Merge with existing state to preserve React Router's history data.
      shouldReplaceRef.current = false;
      const existing = window.history.state ?? {};
      window.history.replaceState(
        { ...existing, [HISTORY_KEY]: effectiveBc },
        "",
      );
    } else {
      // Navigation action: push new entry so back button works.
      window.history.pushState({ [HISTORY_KEY]: effectiveBc }, "");
    }
  }, [state.breadcrumb, state.fork]);

  // ── Listen for browser back/forward ─────────────────────────────
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      const saved: BreadcrumbItem[] | undefined =
        event.state?.[HISTORY_KEY];

      if (saved && Array.isArray(saved) && saved.length > 0) {
        // Restore breadcrumb from history state.
        isRestoringRef.current = true;
        dispatch({ type: "SET_BREADCRUMB", breadcrumb: saved });
      }
      // If no Cadence state in the history entry, this is the React Router
      // entry for /projects (or another non-project route). The browser
      // URL change will be picked up by React Router automatically.
      // We do nothing here — the route transition handles it.
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // ── Navigate ────────────────────────────────────────────────────

  const navigate = useCallback(
    async (targetId: string) => {
      dispatch({ type: "NAVIGATE_START" });

      try {
        // Build the current breadcrumb IDs for the API call.
        const currentIds = state.fork
          ? [
              ...state.fork.stem.map((i) => i.id),
              ...state.fork.active.map((i) => i.id),
            ]
          : state.breadcrumb.map((i) => i.id);

        const response = await navigateToItem(currentIds, targetId);

        if (response.action === "no_path") {
          dispatch({
            type: "NAVIGATE_SUCCESS",
            breadcrumb: state.breadcrumb,
            action: "no_path",
            bouncedFrom: null,
          });
          return;
        }

        // Resolve UUIDs to BreadcrumbItems.
        const existingItems = new Map<string, BreadcrumbItem>();
        for (const item of state.breadcrumb) {
          existingItems.set(item.id, item);
        }
        if (state.fork) {
          for (const item of [
            ...state.fork.stem,
            ...state.fork.active,
            ...state.fork.inactive,
          ]) {
            existingItems.set(item.id, item);
          }
        }

        // Fetch any items we don't already have.
        const idsToFetch = response.breadcrumb.filter(
          (id) => !existingItems.has(id),
        );
        if (idsToFetch.length > 0) {
          const fetched = await getItems(idsToFetch);
          const workflowTypes = new Set(["conflict", "change", "directive", "decision"]);
          for (const item of fetched) {
            const displayName = workflowTypes.has(item.item_type)
              ? formatWorkflowBreadcrumb(item.item_type, item.identifier ?? "", item.properties)
              : itemDisplayName(item);
            existingItems.set(item.id, {
              id: item.id,
              name: displayName,
              itemType: item.item_type,
            });
          }
        }

        // Build the new breadcrumb from response UUIDs.
        const newBreadcrumb: BreadcrumbItem[] = response.breadcrumb.map(
          (id) => existingItems.get(id)!,
        );

        // Determine if this creates a fork (Z-axis lateral jump).
        if (
          response.action === "bounce_back" &&
          response.bounced_from &&
          !response.breadcrumb.includes(response.bounced_from)
        ) {
          const oldPath = state.fork
            ? [
                ...state.fork.stem.map((i) => i.id),
                ...state.fork.active.map((i) => i.id),
              ]
            : state.breadcrumb.map((i) => i.id);

          let forkIndex = 0;
          for (
            let i = 0;
            i < Math.min(oldPath.length, response.breadcrumb.length);
            i++
          ) {
            if (oldPath[i] === response.breadcrumb[i]) {
              forkIndex = i;
            } else {
              break;
            }
          }

          const stemItems = newBreadcrumb.slice(0, forkIndex + 1);
          const activeItems = newBreadcrumb.slice(forkIndex + 1);

          const inactiveItems: BreadcrumbItem[] = [];
          for (let i = forkIndex + 1; i < oldPath.length; i++) {
            const item = existingItems.get(oldPath[i]);
            if (item) inactiveItems.push(item);
          }

          if (inactiveItems.length > 0 && activeItems.length > 0) {
            dispatch({
              type: "FORK_CREATE",
              stem: stemItems,
              active: activeItems,
              inactive: inactiveItems,
            });
            return;
          }
        }

        // Check for fork absorption.
        if (state.fork) {
          const targetOnDeadBranch = state.fork.inactive.some(
            (item) => item.id === targetId,
          );
          if (targetOnDeadBranch) {
            dispatch({
              type: "FORK_ABSORB",
              breadcrumb: newBreadcrumb,
            });
            return;
          }
        }

        dispatch({
          type: "NAVIGATE_SUCCESS",
          breadcrumb: newBreadcrumb,
          action: response.action,
          bouncedFrom: response.bounced_from,
        });
      } catch (err) {
        dispatch({
          type: "NAVIGATE_ERROR",
          error: err instanceof Error ? err.message : "Navigation failed",
        });
      }
    },
    [state.breadcrumb, state.fork],
  );

  const popTo = useCallback((index: number) => {
    dispatch({ type: "POP_TO", index });
    // History push happens in the sync effect.
  }, []);

  const setBreadcrumb = useCallback((items: BreadcrumbItem[]) => {
    shouldReplaceRef.current = true;
    dispatch({ type: "SET_BREADCRUMB", breadcrumb: items });
  }, []);

  return (
    <NavigationContext.Provider
      value={{ state, navigate, popTo, setBreadcrumb }}
    >
      {children}
    </NavigationContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────

export function useNavigationContext(): NavigationContextValue {
  const ctx = useContext(NavigationContext);
  if (!ctx) {
    throw new Error(
      "useNavigationContext must be used within a NavigationProvider",
    );
  }
  return ctx;
}

// Re-export for direct access in Breadcrumb component.
export { NavigationContext };
