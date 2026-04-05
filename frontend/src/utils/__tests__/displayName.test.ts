// ─── itemDisplayName tests ────────────────────────────────────────
// Covers backward-compat path-style property identifiers ("door/fire_rating")
// and fallback when identifier is null.

import { itemDisplayName } from "@/utils/displayName";

describe("itemDisplayName", () => {
  it("returns identifier as-is for non-property items", () => {
    expect(itemDisplayName("Door 101", "door")).toBe("Door 101");
  });

  it("returns identifier as-is for property items without slash", () => {
    // New-style property items have humanized labels directly.
    expect(itemDisplayName("Fire Rating", "property")).toBe("Fire Rating");
  });

  it("extracts and humanizes name from path-style property identifier", () => {
    expect(itemDisplayName("door/fire_rating", "property")).toBe("Fire Rating");
  });

  it("handles multi-word underscored property names", () => {
    expect(itemDisplayName("door/hardware_set", "property")).toBe("Hardware Set");
  });

  it("handles path with multiple slashes — uses last segment", () => {
    expect(itemDisplayName("parent/child/leaf_name", "property")).toBe("Leaf Name");
  });

  it("falls back to item type when identifier is null", () => {
    expect(itemDisplayName(null, "door")).toBe("door");
  });

  it("falls back to item type for property with null identifier", () => {
    expect(itemDisplayName(null, "property")).toBe("property");
  });

  it("does not transform non-property items with slashes", () => {
    // Only property type triggers the path extraction.
    expect(itemDisplayName("some/path", "document")).toBe("some/path");
  });
});
