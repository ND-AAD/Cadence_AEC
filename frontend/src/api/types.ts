// ─── Type Registry API ────────────────────────────────────────────
// Type CRUD + registry fetch.

import { apiGet, apiPost } from "./client";
import type { TypeRegistryResponse, TypeConfigEntry } from "@/types/navigation";

/**
 * Fetch the full type registry from the backend (OS + firm types merged).
 * Returns a map of type name → TypeConfigEntry.
 */
export async function getTypeRegistry(): Promise<TypeRegistryResponse> {
  return apiGet<TypeRegistryResponse>("/v1/types");
}

/** Payload for creating a new firm-level type definition. */
export interface CreateTypePayload {
  type_name: string;
  label: string;
  plural_label?: string;
  property_defs?: Array<{
    name: string;
    label: string;
    data_type?: string;
    required?: boolean;
    aliases?: string[];
  }>;
}

/**
 * Create a new type definition.
 * POST /api/v1/types
 */
export async function createType(payload: CreateTypePayload): Promise<TypeConfigEntry> {
  return apiPost<TypeConfigEntry>("/v1/types", payload);
}

/**
 * Seed starter vocabulary types.
 * POST /api/v1/types/seed
 */
export async function seedTypes(): Promise<{ seeded_count: number; types: string[] }> {
  return apiPost("/v1/types/seed", {});
}
