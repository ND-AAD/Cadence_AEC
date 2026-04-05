// ─── Connected Items API ──────────────────────────────────────────
// GET /api/items/:id/connected — fetch connected items grouped by type.

import { apiGet } from "./client";
import type { ConnectedItemsResponse } from "@/types/navigation";

export interface ConnectedItemsOptions {
  direction?: "outgoing" | "incoming" | "both";
  types?: string[];
  exclude?: string[];
  /** Milestone context UUID — action_counts only include workflow items at or before this milestone. */
  context?: string;
}

/**
 * Fetch connected items for an item, grouped by type.
 * Returns the item itself plus its connected groups.
 */
export async function getConnectedItems(
  itemId: string,
  options?: ConnectedItemsOptions,
): Promise<ConnectedItemsResponse> {
  const params = new URLSearchParams();

  if (options?.direction) {
    params.set("direction", options.direction);
  }
  if (options?.types && options.types.length > 0) {
    params.set("types", options.types.join(","));
  }
  if (options?.exclude && options.exclude.length > 0) {
    params.set("exclude", options.exclude.join(","));
  }
  if (options?.context) {
    params.set("context", options.context);
  }

  const query = params.toString();
  const path = `/v1/items/${itemId}/connected${query ? `?${query}` : ""}`;
  return apiGet<ConnectedItemsResponse>(path);
}
