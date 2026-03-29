// ─── App Shell ────────────────────────────────────────────────────
// Main application page: NavigationProvider + LayoutFrame.
// This is the primary route (/) that users see.
//
// Wires data hooks to ScaleAccordion (left panel), ItemView (center
// story panel), and ExecSummaryDock (right panel). Derives IDs from
// breadcrumb, fetches item data + connected items + type config +
// resolved properties, and passes everything to content components.

import { useEffect, useMemo, useState, useCallback } from "react";
import { NavigationProvider, useNavigationContext } from "@/context/NavigationContext";
import { useAuth } from "@/context/AuthContext";
import { ComparisonProvider, useTemporalContext } from "@/context/ComparisonContext";
import { LayoutFrame } from "@/components/layout/LayoutFrame";
import { StoryTransition } from "@/components/transitions/StoryTransition";
import { ScaleAccordion } from "@/components/scale/ScaleAccordion";
import { ItemView } from "@/components/story/ItemView";
import { ProjectDataView } from "@/components/story/ProjectDataView";
import { ConflictItemView } from "@/components/workflow/ConflictItemView";
import { ChangeItemView } from "@/components/workflow/ChangeItemView";
import { DirectiveItemView } from "@/components/workflow/DirectiveItemView";
import { MilestonePicker, type MilestoneOption } from "@/components/comparison/MilestonePicker";
import { useCurrentItem } from "@/hooks/useCurrentItem";
import { useConnectedItems } from "@/hooks/useConnectedItems";
import { useComparisonData } from "@/hooks/useComparisonData";
import { useTypeRegistry } from "@/hooks/useTypeRegistry";
import { useDashboardHealth } from "@/hooks/useDashboardHealth";
import { useDockCategories } from "@/hooks/useDockCategories";
import { useLatestContext } from "@/hooks/useLatestContext";
import { useResolvedProperties } from "@/hooks/useResolvedProperties";
import { useAffectedItems } from "@/hooks/useAffectedItems";
import { SearchModal } from "@/components/search/SearchModal";
import { AddDataModal } from "@/components/import/AddDataModal";
import { ErrorBoundary } from "@/components/errors/ErrorBoundary";
import { useParams } from "react-router-dom";
import { getItem, itemDisplayName } from "@/api/items";
import { filterDataGroups, excludeBreadcrumbItems } from "@/utils/groupFilters";

function AppShellContent() {
  const { state, navigate, popTo, setBreadcrumb } = useNavigationContext()!;
  const { state: temporalState, activate, deactivate, setComparing, setValueMode, enterQuiet, exitQuiet } = useTemporalContext();
  const { user } = useAuth();
  const [searchOpen, setSearchOpen] = useState(false);
  const [milestonePickerOpen, setMilestonePickerOpen] = useState(false);
  const { projectId: routeProjectId } = useParams<{ projectId: string }>();
  const [addDataOpen, setAddDataOpen] = useState(false);
  const [projectHasData, setProjectHasData] = useState(false);

  // ─── Selection state (SELECT vs ZOOM) ──────────────────────────
  // Click Narrative §3.2: Left panel click = SELECT (show detail,
  // breadcrumb unchanged). Main area click = ZOOM (navigate).
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  // ─── Category-level selection (project level) ─────────────────
  // Click Narrative: At project level, clicking a type group in the
  // left panel selects that category. Main area filters to show
  // only items of that type.
  const [selectedGroupType, setSelectedGroupType] = useState<string | null>(null);

  // ─── Workflow perspective (project level) ─────────────────────
  // When a DockTypeRow is clicked, sets a workflow perspective to
  // show items filtered by workflow category (changes, conflicts,
  // directives) and grouped by type within each category.
  const [workflowPerspective, setWorkflowPerspective] = useState<{
    category: string;    // "changes", "conflicts", "directives"
    groupKey: string;    // item_type like "door", "hardware_set"
    groupLabel: string;  // display label like "Doors"
  } | null>(null);

  // ─── Project initialization ──────────────────────────────────────

  useEffect(() => {
    if (state.breadcrumb.length === 0 && routeProjectId) {
      (async () => {
        try {
          const project = await getItem(routeProjectId);
          setBreadcrumb([{
            id: project.id,
            name: itemDisplayName(project),
            itemType: project.item_type,
          }]);
        } catch {
          // Fallback: use the route ID with generic label.
          setBreadcrumb([
            { id: routeProjectId, name: "Project", itemType: "project" },
          ]);
        }
      })();
    }
  }, [routeProjectId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Global keyboard shortcuts ───────────────────────────────────

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl+K: Toggle search modal.
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((open) => !open);
      }
      // Ctrl+Shift+C: Toggle comparison mode.
      if (e.ctrlKey && e.shiftKey && e.key === "C") {
        e.preventDefault();
        if (temporalState.isComparing) {
          setComparing(false);
          deactivate();
        } else {
          setMilestonePickerOpen((open) => !open);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [temporalState.isComparing, setComparing, deactivate]);

  // Clear selection when navigation state changes (breadcrumb or fork update).
  useEffect(() => {
    setSelectedItemId(null);
    setSelectedGroupType(null);
    setWorkflowPerspective(null);
  }, [state.breadcrumb, state.fork]);


  // ─── Derive IDs from breadcrumb ──────────────────────────────────

  /** The project root item ID (first breadcrumb segment). */
  const projectId = useMemo(() => {
    const bc = state.breadcrumb;
    return bc.length > 0 ? bc[0].id : null;
  }, [state.breadcrumb]);

  /** The item at the tip of the current path (last breadcrumb or active fork branch). */
  const currentItemId = useMemo(() => {
    if (state.fork) {
      const active = state.fork.active;
      return active.length > 0 ? active[active.length - 1].id : null;
    }
    const bc = state.breadcrumb;
    return bc.length > 0 ? bc[bc.length - 1].id : null;
  }, [state.breadcrumb, state.fork]);

  // ─── Temporal state persistence ────────────────────────────────────
  // Quiet mode and value mode are user-initiated and persist across
  // navigation. No auto-defaulting. The user controls their own lens.

  /** The milestone in the current breadcrumb path (if any).
   *  Used to default the "to" context in the MilestonePicker. */
  const breadcrumbMilestoneId = useMemo(() => {
    const allItems = state.fork
      ? [...state.fork.stem, ...state.fork.active]
      : state.breadcrumb;
    const milestone = allItems.find(
      (item) => item.itemType === "milestone" || item.itemType === "issuance"
    );
    return milestone?.id ?? null;
  }, [state.breadcrumb, state.fork]);

  /** The parent of the current item (for sibling derivation). */
  const parentItemId = useMemo(() => {
    if (state.fork) {
      const active = state.fork.active;
      if (active.length > 1) return active[active.length - 2].id;
      const stem = state.fork.stem;
      return stem.length > 0 ? stem[stem.length - 1].id : null;
    }
    const bc = state.breadcrumb;
    return bc.length > 1 ? bc[bc.length - 2].id : null;
  }, [state.breadcrumb, state.fork]);

  /** Set of all breadcrumb item IDs for in-path detection. */
  const breadcrumbIds = useMemo(() => {
    const ids = new Set<string>();
    for (const item of state.breadcrumb) ids.add(item.id);
    if (state.fork) {
      for (const item of state.fork.stem) ids.add(item.id);
      for (const item of state.fork.active) ids.add(item.id);
      for (const item of state.fork.inactive) ids.add(item.id);
    }
    return ids;
  }, [state.breadcrumb, state.fork]);

  /** Parent breadcrumb item name (for the sibling strip label). */
  const parentName = useMemo(() => {
    if (state.fork) {
      const active = state.fork.active;
      if (active.length > 1) return active[active.length - 2].name;
      const stem = state.fork.stem;
      return stem.length > 0 ? stem[stem.length - 1].name : "Parent";
    }
    const bc = state.breadcrumb;
    return bc.length > 1 ? bc[bc.length - 2].name : "Parent";
  }, [state.breadcrumb, state.fork]);

  // ─── Data hooks ──────────────────────────────────────────────────

  const { item: currentItem, loading: itemLoading, error: itemError, retry: refreshItem } =
    useCurrentItem(currentItemId);
  const { data: connectedData, loading: connectedLoading, retry: refreshConnected } =
    useConnectedItems(currentItemId);
  const { data: parentConnectedData } =
    useConnectedItems(parentItemId);
  // Project root connections — always available for milestone derivation.
  // When currentItemId IS the project, this duplicates connectedData but
  // the hook handles caching. Needed so Compare works at any depth.
  const { data: projectConnectedData } =
    useConnectedItems(projectId);
  const { getType } = useTypeRegistry();

  // ─── Selected item data (for SELECT gesture) ───────────────────
  // All hooks handle null gracefully (skip fetch when no selection).
  const { item: selectedItem, loading: selectedItemLoading } =
    useCurrentItem(selectedItemId);
  const { data: selectedConnectedData } =
    useConnectedItems(selectedItemId);

  // ─── Context derivation (auto-detect latest milestone) ──────────

  const { contextId } = useLatestContext(projectId);

  // ─── Temporal state → API mode derivation ──────────────────────────
  // Derive the effective API mode from temporal state.
  // In Quiet mode (backend: mode=current), pass null for contextId.
  // Otherwise, use the breadcrumb milestone (the milestone you navigated
  // through) so resolved properties reflect that milestone's data.
  // Falls back to the latest milestone when no milestone is in the path.
  const effectiveMode = temporalState.isQuiet ? "current" : temporalState.valueMode;
  const activeContextId = breadcrumbMilestoneId ?? contextId;
  const resolvedContextId = temporalState.isQuiet ? null : activeContextId;

  // ─── Resolved properties (snapshot-based display) ────────────────

  const { properties: resolvedProperties } = useResolvedProperties(
    currentItemId,
    resolvedContextId,
    effectiveMode,
  );

  // Resolved properties for the selected item (when left panel selection active).
  const { properties: selectedResolvedProperties } = useResolvedProperties(
    selectedItemId,
    resolvedContextId,
    effectiveMode,
  );

  // ─── Comparison data (FE-2) ─────────────────────────────────────

  const { data: comparisonData } = useComparisonData(currentItemId);

  /** Available milestones derived from project root connected items.
   *  Uses projectConnectedData (not currentItem's connections) so
   *  milestones are always available regardless of navigation depth. */
  const milestones = useMemo<MilestoneOption[]>(() => {
    const source = projectConnectedData ?? connectedData;
    if (!source) return [];
    // Look for connected groups that represent milestones/contexts.
    for (const group of source.connected) {
      if (
        group.item_type === "milestone" ||
        group.item_type === "context" ||
        group.item_type === "issuance"
      ) {
        return group.items.map((m) => ({
          id: m.id,
          label: m.identifier ?? m.item_type,
        }));
      }
    }
    return [];
  }, [projectConnectedData, connectedData]);

  // ─── Distributed temporal control handlers (DTC-9) ───────────────
  // CompareButton toggle, QuietButton toggle, ValueModeToggle change.

  /** Compare toggle: enter comparison (open picker) or exit comparison. */
  const handleCompareToggle = useCallback(() => {
    if (temporalState.isComparing) {
      setComparing(false);
      deactivate();
    } else {
      setMilestonePickerOpen(true);
    }
  }, [temporalState.isComparing, setComparing, deactivate]);

  /** Quiet toggle: enter/exit Quiet mode. Entering Quiet deactivates comparison.
   *  If standing on a milestone/issuance, step back one breadcrumb level first
   *  so the user sees the building (items), not the process (milestone). */
  const handleQuietToggle = useCallback(() => {
    if (temporalState.isQuiet) {
      exitQuiet();
    } else {
      if (temporalState.isComparing) {
        setComparing(false);
        deactivate();
      }
      // If currently viewing a milestone, navigate to its parent first.
      if (
        currentItem &&
        (currentItem.item_type === "milestone" || currentItem.item_type === "issuance") &&
        state.breadcrumb.length > 1
      ) {
        popTo(state.breadcrumb.length - 2);
      }
      enterQuiet();
    }
  }, [temporalState.isQuiet, temporalState.isComparing, enterQuiet, exitQuiet, setComparing, deactivate, currentItem, state.breadcrumb.length, popTo]);

  /** Value mode change handler. */
  const handleValueModeChange = useCallback((mode: "submitted" | "cumulative") => {
    setValueMode(mode);
  }, [setValueMode]);

  /** Milestone picker confirm handler.
   *  Sets isComparing + activates comparison data. */
  const handleMilestoneCompare = useCallback(
    (fromId: string, toId: string) => {
      const fromMilestone = milestones.find((m) => m.id === fromId);
      const toMilestone = milestones.find((m) => m.id === toId);
      setComparing(true);
      activate(
        { id: fromId, identifier: fromMilestone?.label ?? null },
        { id: toId, identifier: toMilestone?.label ?? null },
      );
      setMilestonePickerOpen(false);
    },
    [milestones, activate, setComparing],
  );

  // ─── Dashboard data (exec summary dock) ─────────────────────────

  const {
    health: dashboardHealth,
    importSummary,
    directiveStatus,
    loading: dockLoading,
  } = useDashboardHealth();

  // ─── Affected items for workflow perspective ───────────────────

  const { affectedItems } = useAffectedItems(projectId);

  const dockCategories = useDockCategories(dashboardHealth, directiveStatus, affectedItems);

  // ─── Derived data ────────────────────────────────────────────────

  /** Type config for the current item (drives rendering). */
  const typeConfig = currentItem ? getType(currentItem.item_type) : undefined;

  /** Connected groups for story panel connection rows (all types). */
  const connectedGroups = connectedData?.connected ?? [];

  /** Filtered groups for scale panel + story panel — data types only, no workflow/hidden, no breadcrumb items. */
  const dataGroups = useMemo(
    () => excludeBreadcrumbItems(filterDataGroups(connectedGroups, getType), breadcrumbIds),
    [connectedGroups, getType, breadcrumbIds],
  );

  /** Whether the CURRENT VIEW has milestones (only meaningful when viewing the project). */
  const currentViewHasMilestones = connectedGroups.some(
    (g) => g.item_type === "milestone" || g.item_type === "issuance"
  );

  // Update sticky flag when we're at the project root
  useEffect(() => {
    if (currentItem?.item_type === "project" && currentViewHasMilestones) {
      setProjectHasData(true);
    }
  }, [currentItem?.item_type, currentViewHasMilestones]);

  /** Sibling data: items connected to the parent of the same type as the current item. */
  const siblings = useMemo(() => {
    if (!parentConnectedData || !currentItem) return undefined;

    // Find the parent's connected group that matches the current item's type.
    const siblingGroup = parentConnectedData.connected.find(
      (g) => g.item_type === currentItem.item_type,
    );
    if (!siblingGroup || siblingGroup.items.length <= 1) return undefined;

    return {
      parentName,
      items: siblingGroup.items,
    };
  }, [parentConnectedData, currentItem, parentName]);

  // ─── Selection handler (left panel SELECT gesture) ──────────────

  const handleSelect = useCallback((itemId: string) => {
    setSelectedItemId(itemId);
  }, []);

  // ─── Category selection handler (project level) ────────────────

  const handleSelectGroup = useCallback((itemType: string) => {
    // Toggle: clicking the already-selected group deselects it.
    setSelectedGroupType((prev) => prev === itemType ? null : itemType);
    // Clear instance-level selection when switching categories.
    setSelectedItemId(null);
    // Clear workflow perspective when structural selection is active.
    setWorkflowPerspective(null);
  }, []);

  // ─── Workflow perspective handler (project level) ─────────────

  const handleSelectWorkflowGroup = useCallback(
    (category: string, groupKey: string, groupLabel: string) => {
      // Toggle: clicking the already-selected group deselects it.
      setWorkflowPerspective((prev) =>
        prev?.category === category && prev?.groupKey === groupKey
          ? null
          : { category, groupKey, groupLabel }
      );
      // Clear structural selection when workflow is active.
      setSelectedGroupType(null);
    },
    []
  );

  // ─── Navigation handler (main area / right panel ZOOM gesture) ─

  const handleNavigate = useCallback((targetId: string) => {
    navigate(targetId);
  }, [navigate]);

  // ─── Search navigation ──────────────────────────────────────────

  const handleSearchNavigate = useCallback((targetId: string) => {
    navigate(targetId);
    setSearchOpen(false);
  }, [navigate]);

  // ─── Workflow action refresh ────────────────────────────────────
  // After any workflow action (resolve, hold, acknowledge, etc.),
  // refresh the current item and connected data so the UI updates.
  const handleWorkflowAction = useCallback(() => {
    refreshItem();
    refreshConnected();
  }, [refreshItem, refreshConnected]);

  // ─── Loading state ───────────────────────────────────────────────

  const isLoading = itemLoading || connectedLoading;

  // ─── Scale panel content ─────────────────────────────────────────

  const scaleContent = isLoading ? (
    <div className="px-3 py-4 text-xs text-trace animate-pulse">
      Loading…
    </div>
  ) : (
    <ScaleAccordion
      groups={dataGroups}
      getType={getType}
      onSelect={handleSelect}
      selectedItemId={selectedItemId}
      onSelectGroup={currentItem?.item_type === "project" ? handleSelectGroup : undefined}
      selectedGroupType={currentItem?.item_type === "project" ? selectedGroupType : undefined}
      comparisonActive={temporalState.isActive}
    />
  );

  // ─── Story panel content ─────────────────────────────────────────

  let storyContent: React.ReactNode;

  if (!currentItemId || currentItemId === "root") {
    // Project root or empty breadcrumb — clean empty state.
    storyContent = (
      <div className="flex items-center justify-center h-full p-8">
        <p className="text-sm text-trace">
          Select an item from the scale panel to begin.
        </p>
      </div>
    );
  } else if (itemError) {
    // Error state.
    storyContent = (
      <div className="flex flex-col items-center justify-center h-full p-8">
        <div className="px-4 py-3 bg-redline-wash text-redline-ink text-sm rounded max-w-md text-center">
          {itemError}
        </div>
      </div>
    );
  } else if (isLoading || !currentItem) {
    // Loading state.
    storyContent = (
      <div className="flex flex-col items-center justify-center h-full p-8">
        <span className="text-sm text-trace animate-pulse">Loading item…</span>
      </div>
    );
  } else if (selectedItemId && selectedItem && !selectedItemLoading && currentItem?.item_type !== "project") {
    // ─── Selected item view (left panel SELECT gesture) ──────────
    // Show the selected item's detail without changing breadcrumb.
    // At project level, selection drives expand-in-place within
    // ProjectDataView instead of swapping to ItemView.
    const selTypeConfig = getType(selectedItem.item_type);
    const selConnectedGroups = selectedConnectedData?.connected ?? [];

    storyContent = (
      <div className="relative">
        <ItemView
          item={selectedItem}
          connectedGroups={selConnectedGroups}
          typeConfig={selTypeConfig}
          getType={getType}
          breadcrumbIds={breadcrumbIds}
          onNavigate={handleNavigate}
          resolvedProperties={selectedResolvedProperties}
          comparisonData={null}
          comparisonActive={temporalState.isActive}
          fromContextName={temporalState.fromContext?.identifier ?? "From"}
          toContextName={temporalState.toContext?.identifier ?? "To"}
          onComparisonToggle={handleCompareToggle}
          valueMode={effectiveMode}
          isComparing={temporalState.isComparing}
          onCompareToggle={handleCompareToggle}
          compareVisible={!temporalState.isQuiet}
          isQuiet={temporalState.isQuiet}
        />

        {/* Milestone picker dropdown (anchored to header area) */}
        {milestonePickerOpen && milestones.length >= 2 && (
          <div className="absolute top-0 right-4 z-50">
            <MilestonePicker
              milestones={milestones}
              onCompare={handleMilestoneCompare}
              onClose={() => setMilestonePickerOpen(false)}
              currentContextId={breadcrumbMilestoneId}
            />
          </div>
        )}
      </div>
    );
  } else {
    // Type-driven view dispatch.
    const itemType = currentItem.item_type;

    if (itemType === "project" && !currentViewHasMilestones) {
      // Empty project → guided empty state (DS-3 Screen 3)
      storyContent = (
        <div className="flex flex-col items-center justify-center h-full p-8 text-center">
          <div className="text-lg text-graphite mb-2">No milestones yet</div>
          <p className="text-sm text-trace mb-6 max-w-sm">
            Upload your first document to start tracking changes across milestones.
          </p>
          <button
            onClick={() => setAddDataOpen(true)}
            className="px-4 py-2 text-sm font-medium bg-ink text-sheet hover:bg-ink/90 transition-colors"
          >
            + Add Data
          </button>
        </div>
      );
    } else if (itemType === "project") {
      // Project root → data item listing (Click Narrative §3.1)
      storyContent = (
        <ProjectDataView
          groups={dataGroups}
          allConnectedGroups={connectedGroups}
          affectedItems={affectedItems}
          getType={getType}
          breadcrumbIds={breadcrumbIds}
          onNavigate={handleNavigate}
          comparisonActive={temporalState.isActive}
          selectedGroupType={selectedGroupType}
          workflowPerspective={workflowPerspective}
          selectedItemId={selectedItemId}
          isQuiet={temporalState.isQuiet}
        />
      );
    } else if (itemType === "conflict") {
      // Conflict workflow item → ConflictItemView (Surface 2)
      // Sources come from connected items that are source types (schedules, specs, etc.)
      // Values come from the conflict item's snapshot or properties.
      const conflictProps = currentItem.properties ?? {};
      const sourceItems = connectedGroups
        .flatMap((g) => g.items)
        .filter((i) => {
          const tc = getType(i.item_type);
          return tc?.is_source_type === true;
        });
      // Build source list — use connected source items with values from conflict snapshots
      const conflictSources = sourceItems.map((s) => ({
        sourceId: s.id,
        sourceName: s.identifier ?? s.item_type,
        value: String(conflictProps[`value_${s.id}`] ?? s.identifier ?? ""),
      }));
      storyContent = (
        <ConflictItemView
          item={currentItem}
          sources={conflictSources}
          contextLabel={temporalState.toContext?.identifier ?? undefined}
          onNavigate={handleNavigate}
          onWorkflowAction={handleWorkflowAction}
        />
      );
    } else if (itemType === "change") {
      // Change workflow item → ChangeItemView (Surface 2)
      const changeProps = currentItem.properties ?? {};
      storyContent = (
        <ChangeItemView
          item={currentItem}
          propertyName={changeProps.property_name as string | undefined}
          oldValue={changeProps.previous_value as string | undefined}
          newValue={changeProps.new_value as string | undefined}
          onNavigate={handleNavigate}
          onWorkflowAction={handleWorkflowAction}
        />
      );
    } else if (itemType === "directive") {
      // Directive workflow item → DirectiveItemView (Surface 2)
      const dirProps = currentItem.properties ?? {};
      storyContent = (
        <DirectiveItemView
          item={currentItem}
          propertyName={dirProps.property_name as string | undefined}
          targetValue={dirProps.target_value as string | undefined}
          onNavigate={handleNavigate}
          onWorkflowAction={handleWorkflowAction}
        />
      );
    } else {
      // All other types → generic ItemView
      storyContent = (
        <div className="relative">
          <ItemView
            item={currentItem}
            connectedGroups={connectedGroups}
            typeConfig={typeConfig}
            siblings={siblings}
            getType={getType}
            breadcrumbIds={breadcrumbIds}
            onNavigate={handleNavigate}
            resolvedProperties={resolvedProperties}
            comparisonData={comparisonData}
            comparisonActive={temporalState.isActive}
            fromContextName={temporalState.fromContext?.identifier ?? "From"}
            toContextName={temporalState.toContext?.identifier ?? "To"}
            onComparisonToggle={handleCompareToggle}
            onWorkflowAction={handleWorkflowAction}
            valueMode={effectiveMode}
            isComparing={temporalState.isComparing}
            onCompareToggle={handleCompareToggle}
            compareVisible={!temporalState.isQuiet}
            isQuiet={temporalState.isQuiet}
          />

          {/* Milestone picker dropdown (anchored to header area) */}
          {milestonePickerOpen && milestones.length >= 2 && (
            <div className="absolute top-0 right-4 z-50">
              <MilestonePicker
                milestones={milestones}
                onCompare={handleMilestoneCompare}
                onClose={() => setMilestonePickerOpen(false)}
                currentContextId={breadcrumbMilestoneId}
              />
            </div>
          )}
        </div>
      );
    }
  }

  return (
    <>
      <LayoutFrame
        scaleContent={scaleContent}
        dockCategories={dockCategories}
        importSummary={importSummary}
        dockLoading={dockLoading}
        onSelectWorkflowGroup={handleSelectWorkflowGroup}
        activeWorkflowPerspective={workflowPerspective}
        comparisonActive={temporalState.isActive}
        valueMode={temporalState.valueMode}
        onValueModeChange={handleValueModeChange}
        isQuiet={temporalState.isQuiet}
        inProject={!!projectId}
        hasData={projectHasData}
        onAddData={() => setAddDataOpen(true)}
        onSearchOpen={() => setSearchOpen(true)}
        currentItemId={currentItemId}
        userName={user?.name ?? ""}
        onDockNavigate={handleNavigate}
        onQuietToggle={handleQuietToggle}
        comparisonBadge={
          temporalState.isActive ? (
            <span className="inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded border border-overlay-border bg-overlay-wash text-overlay shrink-0">
              <span className="font-mono">
                {temporalState.fromContext?.identifier ?? "—"}
              </span>
              <span className="text-overlay-border">↔</span>
              <span className="font-mono">
                {temporalState.toContext?.identifier ?? "—"}
              </span>
              <button
                type="button"
                onClick={deactivate}
                className="ml-1 text-overlay-border hover:text-overlay transition-colors"
                title="Deactivate comparison"
              >
                ×
              </button>
            </span>
          ) : undefined
        }
      >
        <StoryTransition itemKey={selectedItemId ?? currentItemId} lastAction={state.lastAction}>
          {storyContent}
        </StoryTransition>
      </LayoutFrame>

      {/* Global search modal */}
      {searchOpen && (
        <SearchModal
          onNavigate={handleSearchNavigate}
          onClose={() => setSearchOpen(false)}
        />
      )}

      {/* Add Data modal */}
      {addDataOpen && projectId && (
        <AddDataModal
          projectId={projectId}
          onClose={() => setAddDataOpen(false)}
          onImportComplete={() => {
            setAddDataOpen(false);
            // Refresh connected items to update empty state → dashboard transition
            if (typeof refreshConnected === "function") refreshConnected();
          }}
        />
      )}
    </>
  );
}

export default function AppShell() {
  return (
    <ErrorBoundary>
      <NavigationProvider>
        <ComparisonProvider>
          <AppShellContent />
        </ComparisonProvider>
      </NavigationProvider>
    </ErrorBoundary>
  );
}
