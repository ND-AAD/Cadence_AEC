// ─── Search API ───────────────────────────────────────────────────
// Item search via backend trigram fuzzy matching.

import { apiGet } from "./client";

/** A search result item. */
export interface SearchResultItem {
  id: string;
  item_type: string;
  identifier: string | null;
}

/** Search response. */
export interface SearchResponse {
  items: SearchResultItem[];
  total: number;
}

/**
 * Search for items by query string, scoped to a project.
 * Uses backend trigram fuzzy matching.
 */
export async function searchItems(
  query: string,
  projectId?: string,
): Promise<SearchResponse> {
  const encoded = encodeURIComponent(query);
  let url = `/v1/items?search=${encoded}&limit=20`;
  if (projectId) {
    url += `&project=${projectId}`;
  }
  return apiGet<SearchResponse>(url);
}
