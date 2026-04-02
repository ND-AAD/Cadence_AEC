// ─── Item View ────────────────────────────────────────────────────
// Top-level story panel content: orchestrates the full item display.
// DS-1 §5: Type-driven rendering of the selected item.
// DS-2 §2–4: Comparison mode, multi-column properties, pips, expansion.
// FE-3/4: Universal expansion dispatch — every row can expand.
//   Silent → source attribution
//   Active conflict → peer-sourced values + resolve controls (Surface 1)
//   Active change → prior/current values + acknowledge
//   Resolved → completed story + resolution stamp + directives
//   Hold → dimmed values + resume button
// Anatomy: ItemHeader → SiblingStrip → ComparisonHeader → Properties → Connections

import { useState, useCallback, useMemo } from "react";
import type {
  ItemResponse,
  ConnectedGroup,
  ItemSummary,
  TypeConfigEntry,
} from "@/types/navigation";
import type { ResolvedProperty } from "@/api/snapshots";
import type { ItemComparison, PropertyChange } from "@/api/comparison";
import type { ResolutionMethod } from "@/api/actionItems";
import { resolveConflict } from "@/api/actionItems";
import { holdItem, acknowledgeChange } from "@/api/workflow";
import { useNotes } from "@/hooks/useNotes";
import type { PropertyStatus } from "./PropertyRow";
import type { ComparisonColumn } from "./PropertyRow";
import type { PipData, CairnData } from "./IndicatorLane";
import { ItemHeader } from "./ItemHeader";
import { SiblingStrip } from "./SiblingStrip";
import { RowGroupLabel } from "./RowGroupLabel";
import { PropertyRow } from "./PropertyRow";
import { ComparisonHeader } from "./ComparisonHeader";
import { IndicatorLane } from "./IndicatorLane";
import { PropertyExpansion } from "./PropertyExpansion";
import { ConflictExpansion, type ConflictSource } from "./ConflictExpansion";
// HoldExpansion used when per-property hold status is available from backend.
// import { HoldExpansion } from "./HoldExpansion";
import { ResolvedExpansion } from "./ResolvedExpansion";
import { SilentExpansion } from "./SilentExpansion";
import { ChangeItemsExpansion } from "./ChangeItemsExpansion";
import { GroupRenderer } from "./renderers/GroupRenderer";
import { ItemNotes } from "./ItemNotes";
import { filterDataGroups, excludeBreadcrumbItems } from "@/utils/groupFilters";

interface ItemViewProps {
  /** The current item being viewed. */
  item: ItemResponse;
  /** Connected items grouped by type (for connection rows). */
  connectedGroups: ConnectedGroup[];
  /** Type configuration for this item. */
  typeConfig?: TypeConfigEntry;
  /** Sibling data (items connected to the same parent). */
  siblings?: {
    parentName: string;
    items: ItemSummary[];
  };
  /** Type lookup function for render mode dispatch on connection groups. */
  getType?: (typeName: string) => TypeConfigEntry | undefined;
  /** Set of breadcrumb item IDs for in-path detection. */
  breadcrumbIds: Set<string>;
  /** Navigation callback for clicks on connections, siblings, etc. */
  onNavigate: (itemId: string) => void;
  /** Resolved property data from snapshots (WP-FE1-B). Null = use raw item.properties. */
  resolvedProperties?: ResolvedProperty[] | null;
  /** Comparison data for this item (FE-2). Null = comparison not active or no data. */
  comparisonData?: ItemComparison | null;
  /** Whether comparison mode is currently active. */
  comparisonActive?: boolean;
  /** Display name for the "from" (older) context. */
  fromContextName?: string;
  /** Display name for the "to" (newer) context. */
  toContextName?: string;
  /** Toggle comparison mode (opens milestone picker or deactivates). */
  onComparisonToggle?: () => void;
  /** Callback after a workflow action (resolve, acknowledge, hold, resume) to refresh data. */
  onWorkflowAction?: () => void;
  /** Value mode for trace treatment (T-7): "cumulative" | "submitted" | "current". Defaults to "submitted". */
  valueMode?: "cumulative" | "submitted" | "current";
  /** Whether comparison mode is engaged (DTC-5, replaces viewMode). */
  isComparing?: boolean;
  /** Callback to toggle comparison mode (DTC-5). */
  onCompareToggle?: () => void;
  /** Whether the compare button is visible (hidden in Quiet mode). */
  compareVisible?: boolean;
  /** Whether Quiet mode is active (DTC-8: diamond problem rendering). */
  isQuiet?: boolean;
  /** Comparison categories for child items (from bulk parent comparison). */
  comparisonCategoryMap?: Map<string, "added" | "removed" | "modified" | "unchanged">;
  /** Current user name (for note authorship). */
  userName?: string;
}

/** Map resolved property status to PropertyRow status. */
function mapResolvedStatus(status: ResolvedProperty["status"]): PropertyStatus {
  switch (status) {
    case "agreed": return "aligned";
    case "single_source": return "aligned";
    case "conflicted": return "conflicted";
    case "resolved": return "resolved";
    default: return "aligned";
  }
}

/** Extract source data from a resolved property for conflict display. */
function extractConflictSources(resolved: ResolvedProperty): ConflictSource[] {
  // The resolved property's sources dict (from backend PropertyResolution)
  // maps source_identifier (human-readable name) → that source's asserted value.
  // source_ids maps source_identifier → UUID.
  const entries = Object.entries(resolved.sources);
  if (entries.length === 0) return [];

  const idMap = resolved.source_ids ?? {};
  return entries.map(([sourceName, value]) => ({
    sourceId: idMap[sourceName] ?? sourceName,
    sourceName,
    value,
  }));
}

export function ItemView({
  item,
  connectedGroups,
  typeConfig,
  siblings,
  getType,
  breadcrumbIds,
  onNavigate,
  resolvedProperties,
  comparisonData,
  comparisonActive = false,
  fromContextName = "",
  toContextName = "",
  onComparisonToggle: _onComparisonToggle,
  onWorkflowAction,
  valueMode = "submitted",
  isComparing = false,
  onCompareToggle,
  compareVisible = true,
  isQuiet = false,
  comparisonCategoryMap,
  userName,
}: ItemViewProps) {
  // ── Expansion state (lifted from PropertyRow) ──
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleExpansion = useCallback((key: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  // ── Fetch notes for cairn detection ──
  const { notes } = useNotes(item.id);
  const hasNotes = notes.length > 0;

  // ── In-memory acknowledge tracking (fallback when change_item_id unavailable) ──
  // NOTE (Decision 13): This fallback is ONLY used when viewing through the
  // comparison API path, where PropertyChange doesn't include change_item_id.
  // When viewing through Surface 2 (workflow item views), the real API is used.
  const [acknowledgedFallback, setAcknowledgedFallback] = useState<Set<string>>(new Set());

  const handleAcknowledgeFallback = useCallback((key: string) => {
    setAcknowledgedFallback((prev) => new Set(prev).add(key));
  }, []);

  // ── Real API workflow handlers ──
  const handleResolveConflict = useCallback(async (
    conflictItemId: string,
    request: { chosen_value: string | null; chosen_source_id: string | null; method: ResolutionMethod },
  ) => {
    try {
      await resolveConflict(conflictItemId, {
        ...request,
        rationale: "", // Surface 1 has no rationale field
        decided_by: "", // Surface 1 has no decided-by field
      });
      onWorkflowAction?.();
    } catch (err) {
      console.error("Failed to resolve conflict:", err);
    }
  }, [onWorkflowAction]);

  // ── Real acknowledge handler (uses API when change_item_id available) ──
  const handleAcknowledge = useCallback(async (key: string, changeItemId?: string) => {
    if (changeItemId) {
      try {
        await acknowledgeChange(changeItemId);
        onWorkflowAction?.();
      } catch (err) {
        console.error("Failed to acknowledge change:", err);
      }
    } else {
      // Fallback: in-memory tracking when change_item_id not available
      handleAcknowledgeFallback(key);
    }
  }, [onWorkflowAction, handleAcknowledgeFallback]);

  // ── Build change map from comparison data ──
  const changeMap = useMemo(() => {
    const map = new Map<string, PropertyChange>();
    if (comparisonData?.changes) {
      for (const change of comparisonData.changes) {
        map.set(change.property_name, change);
      }
    }
    return map;
  }, [comparisonData]);

  // Item-level comparison category: "added" means this item didn't exist
  // at the from-context, "removed" means it doesn't exist at the to-context.
  const comparisonCategory = comparisonData?.category ?? null;

  // Get the property definitions from type config (if available).
  const propertyDefs = typeConfig?.properties ?? [];

  // Internal properties hidden from display regardless of data source.
  // "mark" is the item identifier — already shown in the header.
  const hiddenKeys = new Set(["ordinal", "mark"]);

  // Build property entries — prefer resolved snapshot data when available.
  const propertyEntries: Array<{
    key: string;
    label: string;
    value: unknown;
    unit: string | null;
    status: PropertyStatus;
    resolved?: ResolvedProperty;
  }> = [];

  if (resolvedProperties && resolvedProperties.length > 0) {
    const resolvedMap = new Map(resolvedProperties.map((p) => [p.property_name, p]));

    if (propertyDefs.length > 0) {
      for (const def of propertyDefs) {
        if (hiddenKeys.has(def.name)) continue;
        const resolved = resolvedMap.get(def.name);
        if (resolved) {
          propertyEntries.push({
            key: def.name,
            label: def.label,
            value: resolved.value,
            unit: resolved.unit ?? def.unit,
            status: mapResolvedStatus(resolved.status),
            resolved,
          });
          resolvedMap.delete(def.name);
        } else if (valueMode === "submitted") {
          // In submitted mode, absent properties are hidden unless comparison
          // mode has a change for them (the absence is itself meaningful).
          const change = changeMap.get(def.name);
          if (comparisonActive && change) {
            propertyEntries.push({
              key: def.name,
              label: def.label,
              value: null,
              unit: def.unit,
              status: "aligned",
            });
          }
          // Otherwise: skip — property wasn't submitted at this context.
        } else if (def.name in item.properties) {
          propertyEntries.push({
            key: def.name,
            label: def.label,
            value: item.properties[def.name],
            unit: def.unit,
            status: "aligned",
          });
        }
      }
      for (const [key, resolved] of resolvedMap) {
        propertyEntries.push({
          key,
          label: key,
          value: resolved.value,
          unit: resolved.unit,
          status: mapResolvedStatus(resolved.status),
          resolved,
        });
      }
    } else {
      for (const resolved of resolvedProperties) {
        propertyEntries.push({
          key: resolved.property_name,
          label: resolved.property_name,
          value: resolved.value,
          unit: resolved.unit,
          status: mapResolvedStatus(resolved.status),
          resolved,
        });
      }
    }
  } else if (propertyDefs.length > 0) {
    for (const prop of propertyDefs) {
      if (hiddenKeys.has(prop.name)) continue;
      if (prop.name in item.properties) {
        propertyEntries.push({
          key: prop.name,
          label: prop.label,
          value: item.properties[prop.name],
          unit: prop.unit,
          status: "aligned",
        });
      }
    }
  } else {
    for (const [key, value] of Object.entries(item.properties)) {
      if (hiddenKeys.has(key)) continue;
      propertyEntries.push({ key, label: key, value, unit: null, status: "aligned" });
    }
  }

  return (
    <div className={`min-h-full ${comparisonActive ? "bg-transparent" : "bg-sheet"}`}>
      {/* Sibling strip (Z-axis awareness) */}
      {siblings && siblings.items.length > 1 && (
        <SiblingStrip
          parentName={siblings.parentName}
          siblings={siblings.items}
          activeId={item.id}
          breadcrumbIds={breadcrumbIds}
          onNavigate={onNavigate}
        />
      )}

      {/* Item header with compare button (DTC-5) */}
      <ItemHeader
        item={item}
        typeConfig={typeConfig}
        isComparing={isComparing}
        onCompareToggle={onCompareToggle}
        compareVisible={compareVisible}
      />

      {/* Unified rows */}
      <div className="divide-y divide-rule">
        {/* Comparison column headers (when active) */}
        {comparisonActive && fromContextName && toContextName && (
          <ComparisonHeader
            fromLabel={fromContextName}
            toLabel={toContextName}
          />
        )}

        {/* Properties section */}
        {propertyEntries.length > 0 && (
          <>
            <RowGroupLabel label="Properties" />
            {propertyEntries.map((entry) => {
              const change = changeMap.get(entry.key);
              const isChanged = !!change;
              const isAcknowledgedFallback = acknowledgedFallback.has(entry.key);

              // Workflow-based change detection (from resolved properties).
              // DS-2 §1.3: Changes from another time context are adjacent in single-context view.
              const hasWorkflowChanges = (entry.resolved?.workflow?.change_ids?.length ?? 0) > 0;
              const isExpanded = expandedRows.has(entry.key);

              // Determine if value is carried forward (T-7 trace treatment).
              // In cumulative mode with effective_context set, the value comes from an earlier milestone.
              const isCarriedForward = valueMode === "cumulative" && !!entry.resolved?.effective_context;

              // Determine the effective workflow status for this property.
              // Priority: hold > change > resolved status from snapshots.
              // TODO: When we have per-property hold status from backend, use it.
              const rowStatus: PropertyStatus = isChanged && !isAcknowledgedFallback
                ? "changed"
                : entry.status;

              // ── Build pips for indicator lane ──
              // DS-2: filled = present (at current context), hollow = adjacent (different context).
              // Changes in single-context view are adjacent (hollow); fill in during comparison.
              // Conflicts at the resolved context are always present (filled).
              const pips: PipData[] = [];
              if ((isChanged && !isAcknowledgedFallback) || hasWorkflowChanges) {
                pips.push({
                  key: "change",
                  filled: hasWorkflowChanges || (comparisonActive && isChanged),
                  color: "pencil",
                  tooltip: `${entry.label} \u00B7 changed`,
                });
              }
              if (entry.status === "conflicted") {
                pips.push({
                  key: "conflict",
                  filled: true,
                  color: "redline",
                  tooltip: `${entry.label} \u00B7 conflict`,
                });
              }

              // ── Build cairn data ──
              // Two conditions for cairn:
              // 1. Notes are connected to this item (item-level)
              // 2. Resolved property with pending directives (property-level)
              let cairnData: CairnData | undefined;
              const hasDirectives = entry.resolved?.workflow?.directive_ids && entry.resolved.workflow.directive_ids.length > 0;
              const isResolvedWithDirective = entry.status === "resolved" && hasDirectives;

              if (hasNotes || isResolvedWithDirective) {
                cairnData = {
                  present: true,
                  active: isExpanded,
                  tooltip: hasNotes
                    ? `Note attached to ${item.properties.mark ?? "item"}`
                    : `Resolved: ${entry.label}`,
                };
              }

              // ── Build comparison columns ──
              // When comparison is active, ALL properties render in two-column
              // layout. Changed properties show old/new values with color
              // treatment. Unchanged properties show the same value in both
              // columns (silent — no decoration).
              // Added items: from-column is empty, to-column shows values.
              // Removed items: from-column shows values, to-column is empty.
              let comparisonColumns: [ComparisonColumn, ComparisonColumn] | undefined;
              if (comparisonActive && comparisonCategory === "added") {
                // Item didn't exist at from-context — empty from, value in to.
                comparisonColumns = [
                  {
                    contextLabel: fromContextName,
                    value: <span className="font-mono text-base-size text-trace">—</span>,
                    isOld: true,
                  },
                  {
                    contextLabel: toContextName,
                    value: (
                      <span className="font-mono text-base-size text-pencil-ink">
                        {formatValue(entry.value, entry.unit)}
                      </span>
                    ),
                    isOld: false,
                  },
                ];
              } else if (comparisonActive && comparisonCategory === "removed") {
                // Item doesn't exist at to-context — value in from, empty to.
                comparisonColumns = [
                  {
                    contextLabel: fromContextName,
                    value: (
                      <span className="font-mono text-base-size">
                        {formatValue(entry.value, entry.unit)}
                      </span>
                    ),
                    isOld: false,
                  },
                  {
                    contextLabel: toContextName,
                    value: <span className="font-mono text-base-size text-trace">—</span>,
                    isOld: true,
                  },
                ];
              } else if (comparisonActive && change) {
                comparisonColumns = [
                  {
                    contextLabel: fromContextName,
                    value: (
                      <span className="font-mono text-base-size">
                        {formatValue(change.old_value, entry.unit)}
                      </span>
                    ),
                    isOld: true,
                  },
                  {
                    contextLabel: toContextName,
                    value: (
                      <span className="font-mono text-base-size">
                        {formatValue(change.new_value, entry.unit)}
                      </span>
                    ),
                    isOld: false,
                  },
                ];
              } else if (comparisonActive) {
                // No change detected — same value in both contexts.
                const displayValue = (
                  <span className="font-mono text-base-size">
                    {formatValue(entry.value, entry.unit)}
                  </span>
                );
                comparisonColumns = [
                  { contextLabel: fromContextName, value: displayValue, isOld: false },
                  { contextLabel: toContextName, value: displayValue, isOld: false },
                ];
              }

              // ── Build expansion content (universal dispatch) ──
              let expansionContent: React.ReactNode | undefined;

              if (entry.status === "conflicted") {
                // Active conflict → ConflictExpansion (Surface 1)
                const sources = entry.resolved
                  ? extractConflictSources(entry.resolved)
                  : [];
                const conflictId = entry.resolved?.workflow?.conflict_id ?? null;
                expansionContent = (
                  <ConflictExpansion
                    propertyName={entry.label}
                    sources={sources}
                    status="detected"
                    conflictItemId={conflictId ?? undefined}
                    onResolve={
                      conflictId
                        ? (req) => handleResolveConflict(conflictId, req)
                        : undefined
                    }
                    onHold={
                      conflictId
                        ? () => { holdItem(conflictId).then(() => onWorkflowAction?.()); }
                        : undefined
                    }
                    onNavigate={onNavigate}
                  />
                );
              } else if (entry.status === "resolved") {
                // Resolved → ResolvedExpansion
                const chosenSource = entry.resolved?.workflow?.resolution_metadata?.chosen_source ?? null;
                const sources = entry.resolved
                  ? Object.entries(entry.resolved.sources).map(([sourceName, value]) => ({
                      sourceId: sourceName,
                      sourceName,
                      value,
                      isChosen: chosenSource === sourceName,
                    }))
                  : [];
                const resMeta = entry.resolved?.workflow?.resolution_metadata;
                expansionContent = (
                  <ResolvedExpansion
                    propertyName={entry.label}
                    itemType="conflict"
                    sources={sources}
                    resolution={resMeta ? {
                      chosenValue: String(entry.resolved?.value ?? ""),
                      chosenSourceName: resMeta.chosen_source ?? undefined,
                      decidedBy: resMeta.decided_by ?? undefined,
                      method: resMeta.method ?? undefined,
                      date: resMeta.resolved_at ?? undefined,
                    } : undefined}
                    directives={entry.resolved?.workflow?.directive_ids?.map((id) => ({
                      directiveId: id,
                      targetSourceName: "",
                      propertyName: entry.label,
                      targetValue: null,
                      status: "pending",
                    })) ?? []}
                    onNavigate={onNavigate}
                  />
                );
              } else if (isChanged && change) {
                // Active change → PropertyExpansion (existing)
                expansionContent = (
                  <PropertyExpansion
                    propertyName={entry.label}
                    change={change}
                    fromContextName={fromContextName}
                    toContextName={toContextName}
                    onAcknowledge={
                      !isAcknowledgedFallback
                        ? () => handleAcknowledge(
                            entry.key,
                            entry.resolved?.workflow?.change_ids?.[0] ?? undefined,
                          )
                        : undefined
                    }
                    onNavigateToItem={onNavigate}
                  />
                );
              } else if (hasWorkflowChanges && !isChanged) {
                // Workflow-sourced change — lazy-fetch change items for full detail.
                const changeIds = entry.resolved?.workflow?.change_ids ?? [];
                expansionContent = (
                  <ChangeItemsExpansion
                    changeIds={changeIds}
                    propertyName={entry.key}
                    onNavigate={onNavigate}
                  />
                );
              } else if (entry.resolved && Object.keys(entry.resolved.sources).length > 0) {
                // Silent (aligned) with sources → SilentExpansion
                expansionContent = (
                  <SilentExpansion
                    sources={Object.keys(entry.resolved.sources).map((sourceName) => ({
                      sourceId: sourceName,
                      sourceName,
                    }))}
                    onNavigate={onNavigate}
                  />
                );
              }

              // Every row with expansion content is expandable.
              const isExpandable = !!expansionContent;

              // ── Quiet diamond problem: dual values when sources disagree ──
              // DTC-8: In Quiet mode with multiple disagreeing sources and no
              // source in the breadcrumb path, show all values with inline
              // source attribution.
              const quietDiamond = isQuiet
                && entry.resolved
                && Object.keys(entry.resolved.sources).length > 1
                && new Set(Object.values(entry.resolved.sources).map(String)).size > 1;

              const valueContent = quietDiamond && entry.resolved ? (
                <div className="flex flex-col gap-0.5">
                  {Object.entries(entry.resolved.sources)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([sourceName, sourceValue]) => (
                      <div key={sourceName} className="flex items-baseline justify-between gap-3">
                        <span className="font-mono text-base-size">
                          {formatValue(sourceValue, entry.unit)}
                        </span>
                        <span className="text-trace text-xs shrink-0">
                          {sourceName}
                        </span>
                      </div>
                    ))}
                </div>
              ) : (
                <span className={`font-mono text-base-size ${isCarriedForward || (valueMode === "submitted" && entry.value === null) ? "text-trace" : ""}`}>
                  {formatValue(entry.value, entry.unit)}
                </span>
              );

              return (
                <PropertyRow
                  key={entry.key}
                  label={entry.label}
                  status={rowStatus}
                  comparisonColumns={comparisonColumns}
                  indicators={
                    (pips.length > 0 || cairnData) ? (
                      <IndicatorLane
                        pips={pips}
                        cairn={cairnData}
                        onPipClick={(pipIndex) => {
                          // Pip click = page turn to workflow item (Surface 2).
                          const clickedPip = pips[pipIndex];
                          if (!clickedPip || !entry.resolved?.workflow) return;
                          if (clickedPip.key === "conflict" && entry.resolved.workflow.conflict_id) {
                            onNavigate(entry.resolved.workflow.conflict_id);
                          } else if (clickedPip.key === "change" && entry.resolved.workflow.change_ids?.[0]) {
                            onNavigate(entry.resolved.workflow.change_ids[0]);
                          }
                        }}
                        onCairnClick={
                          cairnData ? () => toggleExpansion(entry.key) : undefined
                        }
                      />
                    ) : undefined
                  }
                  expanded={isExpanded}
                  onToggle={isExpandable ? () => toggleExpansion(entry.key) : undefined}
                  expansionContent={expansionContent}
                >
                  {valueContent}
                </PropertyRow>
              );
            })}
          </>
        )}

        {/* Connection groups — data types only, breadcrumb items excluded */}
        {excludeBreadcrumbItems(
          connectedGroups.filter((group) => {
            if (!getType) return true;
            return filterDataGroups([group], getType).length > 0;
          }),
          breadcrumbIds,
        ).map((group) => (
            <GroupRenderer
              key={group.item_type}
              group={group}
              typeConfig={getType?.(group.item_type)}
              breadcrumbIds={breadcrumbIds}
              onNavigate={onNavigate}
              comparisonActive={comparisonActive}
              comparisonCategoryMap={comparisonCategoryMap}
            />
          ))}
      </div>

      {/* Notes section (bottom of item view) */}
      <ItemNotes itemId={item.id} userName={userName} />
    </div>
  );
}

/** Conversion factors from canonical mm to display units. */
const MM_TO: Record<string, number> = { in: 25.4, ft: 304.8 };

/** Imperial unit indicators — if a string contains these, it already
 *  carries its own units and should not have a suffix appended. */
const IMPERIAL_INDICATORS = /[''\u2018\u2019""\u201c\u201d]|(?:^|\s)(?:ft|in|feet|inch(?:es)?)\b/i;

/** Strip quoting artifacts that CSV parsers sometimes leave behind.
 *  e.g. `"7' - 6""` → `7' - 6"` */
function stripQuoteArtifacts(s: string): string {
  // Remove a matched leading/trailing double-quote pair, then collapse
  // doubled internal quotes (CSV escape) to singles.
  let cleaned = s;
  if (cleaned.startsWith('"') && cleaned.endsWith('"') && cleaned.length > 1) {
    cleaned = cleaned.slice(1, -1);
  }
  // Collapse doubled quotes: "" → "
  cleaned = cleaned.replace(/""/g, '"');
  return cleaned;
}

/** Format a property value for display.
 *  Dimension properties are stored as canonical mm (WP-6b).
 *  When the type_config unit is "in" or "ft", convert before display. */
function formatValue(value: unknown, unit: string | null): string {
  if (value === null || value === undefined) return "—";

  const divisor = unit ? MM_TO[unit] : undefined;
  if (divisor) {
    const num = typeof value === "number" ? value : parseFloat(String(value));
    if (!isNaN(num)) {
      const converted = parseFloat((num / divisor).toFixed(3));
      return `${converted} ${unit}`;
    }
  }

  // Non-numeric value: clean up quoting artifacts and check whether
  // the string already carries unit indicators before appending a suffix.
  let str = stripQuoteArtifacts(String(value));
  if (!unit || IMPERIAL_INDICATORS.test(str)) {
    return str;
  }
  return `${str} ${unit}`;
}
