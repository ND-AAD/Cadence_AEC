// ─── groupFilters tests ───────────────────────────────────────────
// Covers filterDataGroups (spatial pass, workflow/hidden excluded)
// and excludeBreadcrumbItems (item removal, group dropping, count update).

import { filterDataGroups, excludeBreadcrumbItems } from "@/utils/groupFilters";
import type { ConnectedGroup, TypeConfigEntry } from "@/types/navigation";

// ─── Helpers ──────────────────────────────────────────────────────

function makeGroup(
  itemType: string,
  items: { id: string }[] = [{ id: "a" }],
): ConnectedGroup {
  return {
    item_type: itemType,
    label: itemType,
    count: items.length,
    items: items.map((i) => ({
      id: i.id,
      item_type: itemType,
      identifier: null,
      action_counts: { changes: 0, conflicts: 0, directives: 0 },
    })),
  };
}

function makeTypeConfig(category: string): TypeConfigEntry {
  return {
    label: "",
    plural_label: "",
    category,
    icon: "",
    color: "",
    navigable: true,
    is_source_type: false,
    is_context_type: false,
    render_mode: "list",
    default_sort: "identifier",
    valid_targets: [],
    properties: [],
  };
}

// ─── filterDataGroups ─────────────────────────────────────────────

describe("filterDataGroups", () => {
  const typeRegistry: Record<string, TypeConfigEntry> = {
    door: makeTypeConfig("spatial"),
    room: makeTypeConfig("spatial"),
    schedule: makeTypeConfig("document"),
    conflict: makeTypeConfig("workflow"),
    change: makeTypeConfig("workflow"),
    directive: makeTypeConfig("workflow"),
    import_batch: makeTypeConfig("system"),
  };

  const getType = (name: string) => typeRegistry[name];

  it("passes spatial groups through", () => {
    const groups = [makeGroup("door"), makeGroup("room")];
    const result = filterDataGroups(groups, getType);
    expect(result).toHaveLength(2);
  });

  it("passes document groups through", () => {
    const groups = [makeGroup("schedule")];
    const result = filterDataGroups(groups, getType);
    expect(result).toHaveLength(1);
  });

  it("excludes known workflow types regardless of type config category", () => {
    // Even if the type config says "workflow", the hardcoded WORKFLOW_TYPES set catches these.
    const groups = [makeGroup("conflict"), makeGroup("change"), makeGroup("directive")];
    const result = filterDataGroups(groups, getType);
    expect(result).toHaveLength(0);
  });

  it("excludes hidden batch types", () => {
    const groups = [makeGroup("import_batch"), makeGroup("preprocess_batch")];
    const result = filterDataGroups(groups, getType);
    expect(result).toHaveLength(0);
  });

  it("includes unknown types with no type config (safe default)", () => {
    const groups = [makeGroup("custom_user_type")];
    const noConfig = () => undefined;
    const result = filterDataGroups(groups, noConfig);
    expect(result).toHaveLength(1);
  });

  it("mixed groups: only data types survive", () => {
    const groups = [
      makeGroup("door"),
      makeGroup("conflict"),
      makeGroup("import_batch"),
      makeGroup("room"),
    ];
    const result = filterDataGroups(groups, getType);
    expect(result.map((g) => g.item_type)).toEqual(["door", "room"]);
  });
});

// ─── excludeBreadcrumbItems ───────────────────────────────────────

describe("excludeBreadcrumbItems", () => {
  it("returns groups unchanged when breadcrumb is empty", () => {
    const groups = [makeGroup("door", [{ id: "a" }, { id: "b" }])];
    const result = excludeBreadcrumbItems(groups, new Set());
    expect(result).toEqual(groups);
  });

  it("removes individual items that are in the breadcrumb", () => {
    const groups = [makeGroup("door", [{ id: "a" }, { id: "b" }, { id: "c" }])];
    const result = excludeBreadcrumbItems(groups, new Set(["b"]));
    expect(result).toHaveLength(1);
    expect(result[0].items.map((i) => i.id)).toEqual(["a", "c"]);
  });

  it("updates count after removing breadcrumb items", () => {
    const groups = [makeGroup("door", [{ id: "a" }, { id: "b" }, { id: "c" }])];
    const result = excludeBreadcrumbItems(groups, new Set(["a"]));
    expect(result[0].count).toBe(2);
  });

  it("drops groups entirely when all items are in the breadcrumb", () => {
    const groups = [makeGroup("door", [{ id: "a" }, { id: "b" }])];
    const result = excludeBreadcrumbItems(groups, new Set(["a", "b"]));
    expect(result).toHaveLength(0);
  });

  it("handles multiple groups — only affected groups change", () => {
    const groups = [
      makeGroup("door", [{ id: "a" }, { id: "b" }]),
      makeGroup("room", [{ id: "c" }]),
    ];
    const result = excludeBreadcrumbItems(groups, new Set(["a"]));
    expect(result).toHaveLength(2);
    expect(result[0].items).toHaveLength(1);
    expect(result[0].items[0].id).toBe("b");
    expect(result[1].items).toHaveLength(1);
  });
});
