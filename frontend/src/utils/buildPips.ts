// ─── Build Pips ──────────────────────────────────────────────────
// Shared utility to build PipData arrays from action counts.
// DS-2 §3: Present/Adjacent framework governs filled state.
//
// Mechanism vs. policy separation:
//   - buildPips: pure mapping from counts + present set → PipData.
//     No policy decisions. No per-type conditionals.
//   - presentCategories: determines what's "present" (filled) based
//     on the rendering context. All policy lives here.
//   - Callers can pass a custom present set when their rendering
//     context differs from the default (e.g., workflow perspective).

import type { PipData, PipColor } from "@/components/story/IndicatorLane";

// ─── Types ───────────────────────────────────────────────────────

interface ActionCounts {
  conflicts: number;
  changes: number;
  directives: number;
}

// ─── Pip category config (data-driven, not conditional) ──────────

const PIP_CATEGORIES: readonly {
  readonly key: keyof ActionCounts;
  readonly pipKey: string;
  readonly color: PipColor;
}[] = [
  { key: "changes", pipKey: "change", color: "pencil" },
  { key: "conflicts", pipKey: "conflict", color: "redline" },
  { key: "directives", pipKey: "directive", color: "overlay" },
];

// ─── Present categories (policy) ─────────────────────────────────

/**
 * Determine which action categories are "present" (filled pip)
 * in the current rendering context.
 *
 * Present = the rendering shows enough context to inspect the action.
 * Adjacent = you know it exists but can't see its full context.
 *
 * This function encodes the default contextual rules. Callers can
 * build their own Set<string> when they have specific context
 * (e.g., a workflow perspective that shows comparison data).
 */
export function presentCategories(comparisonActive: boolean): Set<string> {
  const present = new Set<string>(["conflicts", "directives"]);
  if (comparisonActive) {
    present.add("changes");
  }
  return present;
}

// ─── Build pips (mechanism) ──────────────────────────────────────

/**
 * Build a PipData array from action counts.
 *
 * @param counts   Action counts per category.
 * @param present  Set of category keys that are "present" in the
 *                 current rendering context. Present → filled pip.
 *                 Absent from set → hollow pip (adjacent).
 */
export function buildPips(
  counts: ActionCounts,
  present: Set<string> = new Set(),
): PipData[] {
  const pips: PipData[] = [];

  for (const { key, pipKey, color } of PIP_CATEGORIES) {
    const count = counts[key];
    if (count > 0) {
      pips.push({
        key: pipKey,
        filled: present.has(key),
        color,
        tooltip: `${count} ${pipKey}${count !== 1 ? "s" : ""}`,
      });
    }
  }

  return pips;
}
