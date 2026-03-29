// ─── Group Renderer ───────────────────────────────────────────────
// Dispatch: renders a ConnectedGroup using the appropriate renderer
// based on the group type's render_mode from the TypeConfig.
// Falls back to ListRenderer for unknown render modes.

import type { ConnectedGroup, TypeConfigEntry } from "@/types/navigation";
import { ListRenderer } from "./ListRenderer";

interface GroupRendererProps {
  group: ConnectedGroup;
  typeConfig?: TypeConfigEntry;
  breadcrumbIds: Set<string>;
  onNavigate: (itemId: string) => void;
  /** Whether comparison mode is active (drives pip filled state). */
  comparisonActive?: boolean;
  /** Comparison categories for child items (from bulk parent comparison). */
  comparisonCategoryMap?: Map<string, "added" | "removed" | "modified" | "unchanged">;
}

export function GroupRenderer({
  group,
  typeConfig,
  breadcrumbIds,
  onNavigate,
  comparisonActive = false,
  comparisonCategoryMap,
}: GroupRendererProps) {
  // Alpha: all connection groups render as list. Table/card/timeline
  // renderers exist but aren't wired to snapshot data yet.
  const props = { group, typeConfig, breadcrumbIds, onNavigate, comparisonActive, comparisonCategoryMap };
  return <ListRenderer {...props} />;
}
