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
import { GroupRenderer } from "./renderers/GroupRenderer";
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
  const entries = Object.entries(resolved.sources);
  if (entries.length === 0) return [];

  return entries.map(([sourceName, value]) => ({
    sourceId: sourceName,   // Using name as ID until backend provides UUIDs
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
  onComparisonToggle,
  onWorkflowAction,
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

  // Get the property definitions from type config (if available).
  const propertyDefs = typeConfig?.properties ?? [];

  // Internal properties hidden from display regardless of data source.
  const hiddenKeys = new Set(["ordinal"]);

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
    // Internal properties that shouldn't be shown to users
    const hiddenKeys = new Set(["ordinal"]);
    for (const [key, value] of Object.entries(item.properties)) {
      if (hiddenKeys.has(key)) continue;
      propertyEntries.push({ key, label: key, value, unit: null, status: "aligned" });
    }
  }

  return (
    <div className="bg-sheet min-h-full">
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

      {/* Item header */}
      <ItemHeader
        item={item}
        typeConfig={typeConfig}
        comparisonActive={comparisonActive}
        onComparisonToggle={onComparisonToggle}
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
              const isExpanded = expandedRows.has(entry.key);

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
              if (isChanged && !isAcknowledgedFallback) {
                pips.push({
                  key: "change",
                  filled: comparisonActive,
                  color: "pencil",
                  tooltip: `${toContextName} \u00B7 ${entry.label} \u00B7 changed`,
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
              // Resolved conflict with pending directive → cairn
              let cairnData: CairnData | undefined;
              if (entry.status === "resolved") {
                cairnData = {
                  present: true,
                  active: isExpanded,
                  tooltip: `Resolved: ${entry.label}`,
                };
              }

              // ── Build comparison columns ──
              // When comparison is active, ALL properties render in two-column
              // layout. Changed properties show old/new values with color
              // treatment. Unchanged properties show the same value in both
              // columns (silent — no decoration).
              let comparisonColumns: [ComparisonColumn, ComparisonColumn] | undefined;
              if (comparisonActive && change) {
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
                  <span className="font-mono text-base-size">
                    {formatValue(entry.value, entry.unit)}
                  </span>
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
            />
          ))}
      </div>
    </div>
  );
}

/** Format a property value for display. */
function formatValue(value: unknown, unit: string | null): string {
  if (value === null || value === undefined) return "—";
  const str = String(value);
  return unit ? `${str} ${unit}` : str;
}
