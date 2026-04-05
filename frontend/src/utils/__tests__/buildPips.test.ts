// ─── buildPips + presentCategories tests ─────────────────────────
// Covers the pure pip-building logic: count → PipData mapping,
// filled/hollow state from present set, and tooltip pluralization.

import { buildPips, presentCategories } from "@/utils/buildPips";

describe("buildPips", () => {
  it("returns empty array when all counts are zero", () => {
    const result = buildPips({ conflicts: 0, changes: 0, directives: 0 });
    expect(result).toEqual([]);
  });

  it("returns one pip for a single non-zero category", () => {
    const result = buildPips(
      { conflicts: 1, changes: 0, directives: 0 },
      new Set(["conflicts"]),
    );
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      key: "conflict",
      filled: true,
      color: "redline",
    });
  });

  it("returns three pips in order: change, conflict, directive", () => {
    const result = buildPips(
      { conflicts: 1, changes: 2, directives: 3 },
      new Set(["conflicts", "changes", "directives"]),
    );
    expect(result).toHaveLength(3);
    expect(result.map((p) => p.key)).toEqual(["change", "conflict", "directive"]);
  });

  it("marks pips as filled when category is in present set", () => {
    const present = new Set(["conflicts"]);
    const result = buildPips(
      { conflicts: 1, changes: 1, directives: 1 },
      present,
    );
    const conflictPip = result.find((p) => p.key === "conflict");
    const changePip = result.find((p) => p.key === "change");
    const directivePip = result.find((p) => p.key === "directive");

    expect(conflictPip!.filled).toBe(true);
    expect(changePip!.filled).toBe(false);
    expect(directivePip!.filled).toBe(false);
  });

  it("defaults to all hollow when no present set provided", () => {
    const result = buildPips({ conflicts: 1, changes: 1, directives: 1 });
    expect(result.every((p) => !p.filled)).toBe(true);
  });

  it("pluralizes tooltip correctly: singular", () => {
    const result = buildPips(
      { conflicts: 1, changes: 0, directives: 0 },
      new Set(),
    );
    expect(result[0].tooltip).toBe("1 conflict");
  });

  it("pluralizes tooltip correctly: plural", () => {
    const result = buildPips(
      { conflicts: 2, changes: 0, directives: 0 },
      new Set(),
    );
    expect(result[0].tooltip).toBe("2 conflicts");
  });

  it("pluralizes all categories correctly", () => {
    const result = buildPips(
      { conflicts: 3, changes: 1, directives: 5 },
      new Set(),
    );
    expect(result.find((p) => p.key === "change")!.tooltip).toBe("1 change");
    expect(result.find((p) => p.key === "conflict")!.tooltip).toBe("3 conflicts");
    expect(result.find((p) => p.key === "directive")!.tooltip).toBe("5 directives");
  });

  it("assigns correct colors: pencil for change, redline for conflict, overlay for directive", () => {
    const result = buildPips(
      { conflicts: 1, changes: 1, directives: 1 },
      new Set(),
    );
    expect(result.find((p) => p.key === "change")!.color).toBe("pencil");
    expect(result.find((p) => p.key === "conflict")!.color).toBe("redline");
    expect(result.find((p) => p.key === "directive")!.color).toBe("overlay");
  });
});

describe("presentCategories", () => {
  it("without comparison: conflicts and directives present, changes absent", () => {
    const present = presentCategories(false);
    expect(present.has("conflicts")).toBe(true);
    expect(present.has("directives")).toBe(true);
    expect(present.has("changes")).toBe(false);
  });

  it("with comparison: all three categories present", () => {
    const present = presentCategories(true);
    expect(present.has("conflicts")).toBe(true);
    expect(present.has("directives")).toBe(true);
    expect(present.has("changes")).toBe(true);
  });
});
