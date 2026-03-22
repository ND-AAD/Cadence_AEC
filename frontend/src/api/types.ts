// ─── Type Registry API ────────────────────────────────────────────
// GET /api/items/types — fetch all registered type configurations.

import { apiGet } from "./client";
import type { TypeRegistryResponse } from "@/types/navigation";

/**
 * Fetch the full type registry from the backend.
 * Returns a map of type name → TypeConfigEntry.
 */
export async function getTypeRegistry(): Promise<TypeRegistryResponse> {
  return apiGet<TypeRegistryResponse>("/v1/config/types");
}
