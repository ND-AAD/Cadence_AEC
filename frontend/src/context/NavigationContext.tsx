// ─── Navigation Context ───────────────────────────────────────────
// Global breadcrumb state management via React Context + useReducer.
//
// The reducer handles:
//   - Linear breadcrumb (push, pop, set)
//   - Fork creation (Z-axis lateral jumps)
//   - Fork absorption (navigate to item on dead branch → fork resolves)
//   - Pending/error states during async navigation

import {
  createContext,
  useContext,
  useReducer,
  useCallback,
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
      // Determine if this navigation created a fork, absorbed a fork, or is linear.
      if (action.action === "no_path") {
        return {
          ...state,
          pending: false,
          error: "No connection path found.",
          lastAction: "no_path",
        };
      }

      // If we had a fork, check if the navigation absorbed the dead branch
      // or continued forward from the active branch.
      if (state.fork && action.action === "push") {
        // Check if the target (last item in new breadcrumb) was on the inactive branch.
        const targetId = action.breadcrumb[action.breadcrumb.length - 1]?.id;
        const isOnDeadBranch = state.fork.inactive.some(
          (item) => item.id === targetId,
        );
        if (isOnDeadBranch) {
          // Branch absorption: fork resolves to a straight line.
          return {
            ...state,
            breadcrumb: action.breadcrumb,
            fork: null,
            pending: false,
            error: null,
            lastAction: "push",
          };
        }
        // Forward navigation from the active branch: the user chose to
        // continue forward, which implicitly resolves the fork.
        return {
          ...state,
          breadcrumb: action.breadcrumb,
          fork: null,
          pending: false,
          error: null,
          lastAction: "push",
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
      // Snap-back: trim breadcrumb to the given index (inclusive).
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

export const NavigationContext = createContext<NavigationContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(navigationReducer, initialState);

  const navigate = useCallback(
    async (targetId: string) => {
      dispatch({ type: "NAVIGATE_START" });

      try {
        // Build the current breadcrumb IDs for the API call.
        // If we have a fork, the effective path is stem + active branch.
        const currentIds = state.fork
          ? [
              ...state.fork.stem.map((i) => i.id),
              ...state.fork.active.map((i) => i.id),
            ]
          : state.breadcrumb.map((i) => i.id);

        // Call the navigation API.
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
        // Reuse items we already have to avoid unnecessary API calls.
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

        // Find IDs we need to fetch.
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
        // A fork occurs when bounce_back removes an item from the path
        // and that item isn't the target (i.e., we jumped laterally).
        if (
          response.action === "bounce_back" &&
          response.bounced_from &&
          !response.breadcrumb.includes(response.bounced_from)
        ) {
          // Find the fork point: the last common ancestor.
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

          // Build the inactive branch: items from the old path after the fork point.
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

        // Check for fork absorption: if we had a fork and the target is on the dead branch.
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
  }, []);

  const setBreadcrumb = useCallback((items: BreadcrumbItem[]) => {
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
