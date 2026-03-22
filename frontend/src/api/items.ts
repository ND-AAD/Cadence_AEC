// ─── Items API ────────────────────────────────────────────────────
// Item lookup for breadcrumb name resolution.

import { apiGet } from "./client";
import type { ItemResponse } from "@/types/navigation";

/**
 * Fetch a single item by ID.
 */
export async function getItem(id: string): Promise<ItemResponse> {
  return apiGet<ItemResponse>(`/v1/items/${id}`);
}

/**
 * Fetch multiple items by ID (parallel requests).
 * Returns items in the same order as the input IDs.
 * Throws if any individual request fails.
 */
export async function getItems(ids: string[]): Promise<ItemResponse[]> {
  return Promise.all(ids.map((id) => getItem(id)));
}

/**
 * Convert an ItemResponse to the display name used in breadcrumbs.
 * Uses `identifier` if available, otherwise falls back to item type label.
 */
export function itemDisplayName(item: ItemResponse): string {
  return item.identifier ?? item.item_type;
}

/**
 * Fetch the project root item.
 * Tries /v1/config/root first, falls back to /items?type=project.
 */
export async function getProjectRoot(): Promise<ItemResponse> {
  try {
    return await apiGet<ItemResponse>("/v1/config/root");
  } catch {
    // Fallback: query for project-type items and take the first one.
    const results = await apiGet<{ items: ItemResponse[] }>("/v1/items?type=project&limit=1");
    if (results.items && results.items.length > 0) {
      return results.items[0];
    }
    throw new Error("No project root found");
  }
}
