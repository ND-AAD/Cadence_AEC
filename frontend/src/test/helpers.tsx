import type { ItemResponse } from "@/types/navigation";
import type { ResolutionSource } from "@/components/workflow/ResolutionForm";

/** Build a minimal valid ItemResponse for testing. */
export function buildItem(
  overrides: Partial<ItemResponse> & { item_type: string }
): ItemResponse {
  return {
    id: crypto.randomUUID(),
    identifier: `Test ${overrides.item_type}`,
    properties: {},
    created_by: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

/** Build a ResolutionSource for conflict tests. */
export function buildSource(
  overrides?: Partial<ResolutionSource>
): ResolutionSource {
  return {
    sourceId: crypto.randomUUID(),
    sourceName: "Test Schedule",
    value: "test-value",
    ...overrides,
  };
}
