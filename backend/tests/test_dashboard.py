"""
Tests for WP-13a: Dashboard and Rollup API.

Covers:
  - Project health endpoint (total items, action item counts, breakdowns)
  - Import summary endpoint (most recent batch, empty state)
  - Temporal trend endpoint (per-milestone action item counts)
  - Directive status endpoint (pending/fulfilled by source)
  - Project-scoped queries
  - Empty project / no data edge cases
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Connection, Item, Snapshot
from app.services.property_service import (
    ensure_property_connection,
    get_or_create_property_item,
)


# ─── Fixtures ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def dashboard_scenario(db_session: AsyncSession, make_item, make_connection):
    """
    Create a complete scenario for dashboard testing:
      - project → building → door 101, door 102
      - two sources: schedule, specification
      - two milestones: SD (ordinal 200), DD (ordinal 300)
      - conflict on door 101 finish (schedule vs spec) at DD
      - change on door 101 material (SD → DD from schedule)
      - two directives: one pending, one fulfilled
      - a decision item
      - an import_batch item
    """
    # Project hierarchy
    project = await make_item("project", "Test Project", {"name": "Test Project"})
    building = await make_item("building", "Building A", {"name": "Building A"})
    await make_connection(project, building)

    # Doors
    door1 = await make_item("door", "101", {"mark": "101"})
    door2 = await make_item("door", "102", {"mark": "102"})
    await make_connection(building, door1)
    await make_connection(building, door2)

    # Sources
    schedule = await make_item("schedule", "Door Schedule", {"name": "Door Schedule"})
    spec = await make_item("specification", "Spec Section 09", {"name": "Spec Section 09"})
    await make_connection(project, schedule)
    await make_connection(project, spec)
    await make_connection(schedule, door1)
    await make_connection(schedule, door2)
    await make_connection(spec, door1)

    # Milestones
    sd = await make_item("milestone", "SD", {"name": "SD", "ordinal": 200})
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 300})
    await make_connection(project, sd)
    await make_connection(project, dd)

    # Snapshots for conflict and change
    db_session.add(Snapshot(
        item_id=door1.id, context_id=sd.id, source_id=schedule.id,
        properties={"finish": "paint", "material": "wood"},
    ))
    db_session.add(Snapshot(
        item_id=door1.id, context_id=dd.id, source_id=schedule.id,
        properties={"finish": "paint", "material": "steel"},
    ))
    db_session.add(Snapshot(
        item_id=door1.id, context_id=dd.id, source_id=spec.id,
        properties={"finish": "stain", "material": "steel"},
    ))
    await db_session.flush()

    # Conflict item: door 101 finish at DD (schedule vs spec)
    conflict = await make_item("conflict", "101 / finish", {
        "property_name": "finish",
        "status": "detected",
        "affected_item": str(door1.id),
    })
    db_session.add(Snapshot(
        item_id=conflict.id, context_id=dd.id, source_id=conflict.id,
        properties={"status": "detected", "property_name": "finish"},
    ))
    await db_session.flush()
    await make_connection(conflict, door1)
    await make_connection(conflict, schedule)
    await make_connection(conflict, spec)
    await make_connection(conflict, dd)

    # Change item: door 101 material SD→DD from schedule
    change = await make_item("change", "Door Schedule / 101 / SD→DD", {
        "property_name": "material",
        "status": "detected",
        "affected_item": str(door1.id),
    })
    db_session.add(Snapshot(
        item_id=change.id, context_id=dd.id, source_id=change.id,
        properties={"status": "detected", "property_name": "material"},
    ))
    await db_session.flush()
    await make_connection(change, door1)
    await make_connection(change, schedule)
    await make_connection(change, dd)

    # Decision item
    decision = await make_item("decision", "Decision: 101/finish", {
        "rationale": "Per architect",
        "resolved_value": "paint",
        "decided_by": "Architect",
    })
    db_session.add(Snapshot(
        item_id=decision.id, context_id=dd.id, source_id=decision.id,
        properties={"rationale": "Per architect"},
    ))
    await db_session.flush()

    # Directive: pending (spec needs to update to "paint")
    directive_pending = await make_item("directive", "Directive: 101/finish → Spec", {
        "property_name": "finish",
        "target_value": "paint",
        "target_source_id": str(spec.id),
        "decision_item_id": str(decision.id),
        "affected_item_id": str(door1.id),
        "status": "pending",
    })
    db_session.add(Snapshot(
        item_id=directive_pending.id, context_id=dd.id, source_id=directive_pending.id,
        properties={"status": "pending", "property_name": "finish"},
    ))
    await db_session.flush()
    await make_connection(directive_pending, door1)
    await make_connection(directive_pending, spec, {"relationship": "target_source"})
    await make_connection(directive_pending, dd)

    # Directive: fulfilled (schedule already matches)
    directive_fulfilled = await make_item("directive", "Directive: 102/width → Schedule", {
        "property_name": "width",
        "target_value": "36",
        "target_source_id": str(schedule.id),
        "decision_item_id": str(decision.id),
        "affected_item_id": str(door2.id),
        "status": "fulfilled",
    })
    db_session.add(Snapshot(
        item_id=directive_fulfilled.id, context_id=dd.id, source_id=directive_fulfilled.id,
        properties={"status": "fulfilled", "property_name": "width"},
    ))
    await db_session.flush()
    await make_connection(directive_fulfilled, door2)
    await make_connection(directive_fulfilled, schedule, {"relationship": "target_source"})
    await make_connection(directive_fulfilled, dd)

    # Import batch
    import_batch = await make_item("import_batch", "batch-001", {
        "filename": "door_schedule.xlsx",
        "row_count": 50,
        "status": "completed",
        "source_item_id": str(schedule.id),
        "time_context_id": str(dd.id),
        "items_imported": 50,
        "source_changes": 3,
        "affected_items": 2,
        "new_conflicts": 1,
        "resolved_conflicts": 0,
        "directives_fulfilled": 1,
    })

    return {
        "project": project,
        "building": building,
        "door1": door1,
        "door2": door2,
        "schedule": schedule,
        "spec": spec,
        "sd": sd,
        "dd": dd,
        "conflict": conflict,
        "change": change,
        "decision": decision,
        "directive_pending": directive_pending,
        "directive_fulfilled": directive_fulfilled,
        "import_batch": import_batch,
    }


# ─── Test: Project Health ─────────────────────────────────────


@pytest.mark.asyncio
async def test_health_returns_total_items(client, dashboard_scenario):
    """GET /dashboard/health returns correct total item count."""
    response = await client.get("/api/v1/dashboard/health")
    assert response.status_code == 200
    data = response.json()
    # Count expected items: project, building, 2 doors, 2 sources, 2 milestones,
    # conflict, change, decision, 2 directives, import_batch = 14
    assert data["total_items"] == 14


@pytest.mark.asyncio
async def test_health_by_type_counts(client, dashboard_scenario):
    """GET /dashboard/health returns correct per-type counts."""
    response = await client.get("/api/v1/dashboard/health")
    data = response.json()
    by_type = data["by_type"]
    assert by_type["door"] == 2
    assert by_type["schedule"] == 1
    assert by_type["specification"] == 1
    assert by_type["milestone"] == 2
    assert by_type["conflict"] == 1
    assert by_type["change"] == 1
    assert by_type["decision"] == 1
    assert by_type["directive"] == 2
    assert by_type["import_batch"] == 1


@pytest.mark.asyncio
async def test_health_action_item_counts(client, dashboard_scenario):
    """GET /dashboard/health returns correct action item counts."""
    response = await client.get("/api/v1/dashboard/health")
    data = response.json()
    ai = data["action_items"]
    assert ai["unresolved_conflicts"] == 1  # one detected conflict
    assert ai["unresolved_changes"] == 1    # one detected change
    assert ai["pending_directives"] == 1    # one pending directive
    assert ai["fulfilled_directives"] == 1  # one fulfilled directive
    assert ai["decisions_made"] == 1        # one decision


@pytest.mark.asyncio
async def test_health_by_property(client, dashboard_scenario):
    """GET /dashboard/health breaks down action items by property name."""
    response = await client.get("/api/v1/dashboard/health")
    data = response.json()
    by_prop = data["by_property"]
    # "finish" property has: 1 conflict, 1 directive
    assert "finish" in by_prop
    assert by_prop["finish"]["conflicts"] == 1
    assert by_prop["finish"]["directives"] == 1
    # "material" property has: 1 change
    assert "material" in by_prop
    assert by_prop["material"]["changes"] == 1


@pytest.mark.asyncio
async def test_health_by_source_pair(client, dashboard_scenario):
    """GET /dashboard/health shows conflict counts by source pair."""
    response = await client.get("/api/v1/dashboard/health")
    data = response.json()
    by_pair = data["by_source_pair"]
    # One conflict between "Door Schedule" and "Spec Section 09"
    assert len(by_pair) == 1
    pair_key = list(by_pair.keys())[0]
    assert "Door Schedule" in pair_key
    assert "Spec Section 09" in pair_key
    assert by_pair[pair_key]["conflicts"] == 1


@pytest.mark.asyncio
async def test_health_by_affected_type(client, dashboard_scenario):
    """GET /dashboard/health shows action items by affected item type."""
    response = await client.get("/api/v1/dashboard/health")
    data = response.json()
    by_affected = data["by_affected_type"]
    # Both the conflict and change affect door items
    assert "door" in by_affected
    assert by_affected["door"] >= 2  # conflict + change both affect doors


@pytest.mark.asyncio
async def test_health_empty_project(client):
    """GET /dashboard/health with no data returns zero counts."""
    response = await client.get("/api/v1/dashboard/health")
    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 0
    assert data["by_type"] == {}
    assert data["action_items"]["unresolved_changes"] == 0


@pytest.mark.asyncio
async def test_health_project_scoped(client, dashboard_scenario):
    """GET /dashboard/health?project=uuid scopes to project items."""
    s = dashboard_scenario
    response = await client.get(
        f"/api/v1/dashboard/health?project={s['project'].id}"
    )
    assert response.status_code == 200
    data = response.json()
    # Phase 1 (BFS forward): project, building, 2 doors, 2 sources, 2 milestones = 8
    # Phase 2 (reverse): conflict, change, 2 directives connect INTO base items = 4
    # decision + import_batch have no connections → correctly excluded
    assert data["total_items"] == 12
    # Action items should still be correct within project scope
    assert data["action_items"]["unresolved_conflicts"] == 1
    assert data["action_items"]["unresolved_changes"] == 1
    assert data["action_items"]["pending_directives"] == 1


# ─── Test: Import Summary ────────────────────────────────────


@pytest.mark.asyncio
async def test_import_summary_returns_latest_batch(client, dashboard_scenario):
    """GET /dashboard/import-summary returns the most recent import batch."""
    s = dashboard_scenario
    response = await client.get("/api/v1/dashboard/import-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["batch_id"] == str(s["import_batch"].id)
    assert data["batch_identifier"] == "batch-001"


@pytest.mark.asyncio
async def test_import_summary_has_counts(client, dashboard_scenario):
    """GET /dashboard/import-summary includes summary counts."""
    response = await client.get("/api/v1/dashboard/import-summary")
    data = response.json()
    assert data["items_imported"] == 50
    assert data["source_changes"] == 3
    assert data["affected_items"] == 2
    assert data["new_conflicts"] == 1
    assert data["directives_fulfilled"] == 1


@pytest.mark.asyncio
async def test_import_summary_resolves_source(client, dashboard_scenario):
    """GET /dashboard/import-summary resolves source identifier."""
    response = await client.get("/api/v1/dashboard/import-summary")
    data = response.json()
    assert data["source_identifier"] == "Door Schedule"


@pytest.mark.asyncio
async def test_import_summary_resolves_context(client, dashboard_scenario):
    """GET /dashboard/import-summary resolves context identifier."""
    response = await client.get("/api/v1/dashboard/import-summary")
    data = response.json()
    assert data["context_identifier"] == "DD"


@pytest.mark.asyncio
async def test_import_summary_empty(client):
    """GET /dashboard/import-summary with no batches returns nulls."""
    response = await client.get("/api/v1/dashboard/import-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["batch_id"] is None
    assert data["items_imported"] == 0


@pytest.mark.asyncio
async def test_import_summary_specific_batch(client, dashboard_scenario):
    """GET /dashboard/import-summary?batch_id=uuid returns specific batch."""
    s = dashboard_scenario
    response = await client.get(
        f"/api/v1/dashboard/import-summary?batch_id={s['import_batch'].id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["batch_id"] == str(s["import_batch"].id)


# ─── Test: Temporal Trend ────────────────────────────────────


@pytest.mark.asyncio
async def test_temporal_trend_returns_milestones(client, dashboard_scenario):
    """GET /dashboard/temporal-trend returns all milestones in order."""
    response = await client.get("/api/v1/dashboard/temporal-trend")
    assert response.status_code == 200
    data = response.json()
    milestones = data["milestones"]
    assert len(milestones) == 2
    # SD (ordinal 200) should come before DD (ordinal 300)
    assert milestones[0]["ordinal"] == 200
    assert milestones[1]["ordinal"] == 300
    assert milestones[0]["context_identifier"] == "SD"
    assert milestones[1]["context_identifier"] == "DD"


@pytest.mark.asyncio
async def test_temporal_trend_dd_counts(client, dashboard_scenario):
    """GET /dashboard/temporal-trend shows counts at DD milestone."""
    response = await client.get("/api/v1/dashboard/temporal-trend")
    data = response.json()
    dd = data["milestones"][1]  # DD is second (ordinal 300)
    # Conflict, change, and 2 directives are all linked to DD
    assert dd["conflicts"] >= 1
    assert dd["changes"] >= 1
    assert dd["directives"] >= 1


@pytest.mark.asyncio
async def test_temporal_trend_empty(client):
    """GET /dashboard/temporal-trend with no milestones returns empty list."""
    response = await client.get("/api/v1/dashboard/temporal-trend")
    assert response.status_code == 200
    data = response.json()
    assert data["milestones"] == []


@pytest.mark.asyncio
async def test_temporal_trend_milestones_only(client, make_item):
    """GET /dashboard/temporal-trend with milestones but no workflow items."""
    await make_item("milestone", "Phase 1", {"name": "Phase 1", "ordinal": 100})
    await make_item("milestone", "Phase 2", {"name": "Phase 2", "ordinal": 200})

    response = await client.get("/api/v1/dashboard/temporal-trend")
    assert response.status_code == 200
    data = response.json()
    assert len(data["milestones"]) == 2
    # All counts should be zero
    for ms in data["milestones"]:
        assert ms["changes"] == 0
        assert ms["conflicts"] == 0
        assert ms["directives"] == 0


# ─── Test: Directive Status ──────────────────────────────────


@pytest.mark.asyncio
async def test_directive_status_totals(client, dashboard_scenario):
    """GET /dashboard/directive-status returns correct totals."""
    response = await client.get("/api/v1/dashboard/directive-status")
    assert response.status_code == 200
    data = response.json()
    assert data["total_pending"] == 1
    assert data["total_fulfilled"] == 1


@pytest.mark.asyncio
async def test_directive_status_by_source(client, dashboard_scenario):
    """GET /dashboard/directive-status groups by target source."""
    s = dashboard_scenario
    response = await client.get("/api/v1/dashboard/directive-status")
    data = response.json()
    by_source = data["by_source"]
    assert len(by_source) == 2  # spec and schedule each have one directive

    # Find the spec entry (pending directive targets spec)
    spec_entry = next(
        (e for e in by_source if e["source_id"] == str(s["spec"].id)),
        None,
    )
    assert spec_entry is not None
    assert spec_entry["pending"] == 1
    assert spec_entry["fulfilled"] == 0
    assert spec_entry["source_identifier"] == "Spec Section 09"

    # Find the schedule entry (fulfilled directive targets schedule)
    schedule_entry = next(
        (e for e in by_source if e["source_id"] == str(s["schedule"].id)),
        None,
    )
    assert schedule_entry is not None
    assert schedule_entry["pending"] == 0
    assert schedule_entry["fulfilled"] == 1
    assert schedule_entry["source_identifier"] == "Door Schedule"


@pytest.mark.asyncio
async def test_directive_status_empty(client):
    """GET /dashboard/directive-status with no directives returns zeros."""
    response = await client.get("/api/v1/dashboard/directive-status")
    assert response.status_code == 200
    data = response.json()
    assert data["total_pending"] == 0
    assert data["total_fulfilled"] == 0
    assert data["by_source"] == []


# ─── Test: Multiple Conflicts, Properties ────────────────────


@pytest.mark.asyncio
async def test_health_multiple_conflicts(
    client, db_session, make_item, make_connection
):
    """Health endpoint correctly counts multiple conflicts on different properties."""
    door = await make_item("door", "301", {"mark": "301"})
    sched = await make_item("schedule", "Schedule A", {"name": "Schedule A"})
    spec = await make_item("specification", "Spec A", {"name": "Spec A"})
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 300})

    # Conflict on finish
    c1 = await make_item("conflict", "301/finish", {
        "property_name": "finish",
        "status": "detected",
    })
    await make_connection(c1, door)
    await make_connection(c1, sched)
    await make_connection(c1, spec)
    await make_connection(c1, dd)

    # Conflict on hardware_set
    c2 = await make_item("conflict", "301/hardware_set", {
        "property_name": "hardware_set",
        "status": "detected",
    })
    await make_connection(c2, door)
    await make_connection(c2, sched)
    await make_connection(c2, spec)
    await make_connection(c2, dd)

    # Resolved conflict (should NOT count as unresolved)
    c3 = await make_item("conflict", "301/material", {
        "property_name": "material",
        "status": "resolved",
    })

    response = await client.get("/api/v1/dashboard/health")
    data = response.json()
    assert data["action_items"]["unresolved_conflicts"] == 2
    assert data["by_property"]["finish"]["conflicts"] == 1
    assert data["by_property"]["hardware_set"]["conflicts"] == 1
    # Resolved conflict should not appear in by_property
    assert "material" not in data["by_property"]


@pytest.mark.asyncio
async def test_health_mixed_statuses(client, db_session, make_item, make_connection):
    """Health endpoint correctly handles mixed action item statuses."""
    door = await make_item("door", "401", {"mark": "401"})

    # Detected change (counts as unresolved)
    await make_item("change", "c1", {
        "property_name": "width", "status": "detected"
    })
    # Acknowledged change (still unresolved per spec)
    await make_item("change", "c2", {
        "property_name": "width", "status": "acknowledged"
    })
    # Reviewed change (NOT unresolved — not in detected/acknowledged)
    await make_item("change", "c3", {
        "property_name": "height", "status": "reviewed"
    })

    response = await client.get("/api/v1/dashboard/health")
    data = response.json()
    assert data["action_items"]["unresolved_changes"] == 2
    assert data["by_property"]["width"]["changes"] == 2
    assert "height" not in data["by_property"]


# ─── Test: Directive Status with Multiple Sources ────────────


@pytest.mark.asyncio
async def test_directive_status_multiple_per_source(
    client, db_session, make_item, make_connection
):
    """Directive status correctly aggregates multiple directives per source."""
    spec = await make_item("specification", "My Spec", {"name": "My Spec"})

    await make_item("directive", "d1", {
        "property_name": "finish",
        "target_source_id": str(spec.id),
        "status": "pending",
    })
    await make_item("directive", "d2", {
        "property_name": "material",
        "target_source_id": str(spec.id),
        "status": "pending",
    })
    await make_item("directive", "d3", {
        "property_name": "width",
        "target_source_id": str(spec.id),
        "status": "fulfilled",
    })

    response = await client.get("/api/v1/dashboard/directive-status")
    data = response.json()
    assert data["total_pending"] == 2
    assert data["total_fulfilled"] == 1
    assert len(data["by_source"]) == 1
    entry = data["by_source"][0]
    assert entry["pending"] == 2
    assert entry["fulfilled"] == 1
    assert entry["source_identifier"] == "My Spec"


# ─── Test: Temporal Trend Ordering ───────────────────────────


@pytest.mark.asyncio
async def test_temporal_trend_ordering(
    client, db_session, make_item, make_connection
):
    """Milestones come back ordered by ordinal regardless of creation order."""
    # Create milestones out of order
    cd = await make_item("milestone", "CD", {"name": "CD", "ordinal": 400})
    sd = await make_item("milestone", "SD", {"name": "SD", "ordinal": 200})
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 300})
    sc = await make_item("milestone", "SC", {"name": "SC", "ordinal": 100})

    response = await client.get("/api/v1/dashboard/temporal-trend")
    data = response.json()
    ordinals = [m["ordinal"] for m in data["milestones"]]
    assert ordinals == [100, 200, 300, 400]
    names = [m["context_identifier"] for m in data["milestones"]]
    assert names == ["SC", "SD", "DD", "CD"]


# ─── Test: Source Pair Key Format ────────────────────────────


@pytest.mark.asyncio
async def test_source_pair_key_sorted(
    client, db_session, make_item, make_connection
):
    """Source pair keys are sorted alphabetically (consistent naming)."""
    door = await make_item("door", "501", {"mark": "501"})
    spec = await make_item("specification", "AAA Spec", {"name": "AAA Spec"})
    drawing = await make_item("drawing", "ZZZ Drawing", {"name": "ZZZ Drawing"})

    conflict = await make_item("conflict", "501/finish", {
        "property_name": "finish", "status": "detected",
    })
    await make_connection(conflict, door)
    await make_connection(conflict, spec)
    await make_connection(conflict, drawing)

    response = await client.get("/api/v1/dashboard/health")
    data = response.json()
    by_pair = data["by_source_pair"]
    if by_pair:
        pair_key = list(by_pair.keys())[0]
        # "AAA Spec" should come before "ZZZ Drawing"
        assert pair_key == "AAA Spec+ZZZ Drawing"


# ─── Test: Graph-Based Property Rollup (WP-PROP-4) ──────────────


@pytest.mark.asyncio
async def test_graph_rollup_basic_structure(
    db_session: AsyncSession, make_item, make_connection
):
    """Graph-based rollup returns dict with property identifiers as keys."""
    from app.services.dashboard_service import get_action_items_by_property_graph

    # Create door and property items
    door = await make_item("door", "601", {"mark": "601"})
    finish_prop, _ = await get_or_create_property_item(db_session, "door", "finish")
    await ensure_property_connection(db_session, finish_prop, door)

    # Create a conflict on the finish property
    conflict = await make_item("conflict", "601/finish", {
        "property_name": "finish",
        "status": "detected",
    })
    await make_connection(conflict, finish_prop)

    # Get rollup
    rollup = await get_action_items_by_property_graph(db_session)

    # Should have entry for door/finish
    assert "door/finish" in rollup
    assert "conflicts" in rollup["door/finish"]
    assert "changes" in rollup["door/finish"]
    assert "directives" in rollup["door/finish"]


@pytest.mark.asyncio
async def test_graph_rollup_counts_active_conflicts(
    db_session: AsyncSession, make_item, make_connection
):
    """Graph-based rollup counts only detected conflicts."""
    from app.services.dashboard_service import get_action_items_by_property_graph

    door = await make_item("door", "602", {"mark": "602"})
    finish_prop, _ = await get_or_create_property_item(db_session, "door", "finish")
    await ensure_property_connection(db_session, finish_prop, door)

    # Create detected conflict
    c1 = await make_item("conflict", "602/finish/detected", {
        "property_name": "finish",
        "status": "detected",
    })
    await make_connection(c1, finish_prop)

    # Create resolved conflict (should not count)
    c2 = await make_item("conflict", "602/finish/resolved", {
        "property_name": "finish",
        "status": "resolved",
    })
    await make_connection(c2, finish_prop)

    rollup = await get_action_items_by_property_graph(db_session)

    assert rollup["door/finish"]["conflicts"] == 1


@pytest.mark.asyncio
async def test_graph_rollup_counts_active_changes(
    db_session: AsyncSession, make_item, make_connection
):
    """Graph-based rollup counts detected and acknowledged changes."""
    from app.services.dashboard_service import get_action_items_by_property_graph

    door = await make_item("door", "603", {"mark": "603"})
    material_prop, _ = await get_or_create_property_item(db_session, "door", "material")
    await ensure_property_connection(db_session, material_prop, door)

    # Create detected change
    ch1 = await make_item("change", "603/material/detected", {
        "property_name": "material",
        "status": "detected",
    })
    await make_connection(ch1, material_prop)

    # Create acknowledged change
    ch2 = await make_item("change", "603/material/acked", {
        "property_name": "material",
        "status": "acknowledged",
    })
    await make_connection(ch2, material_prop)

    # Create reviewed change (should not count)
    ch3 = await make_item("change", "603/material/reviewed", {
        "property_name": "material",
        "status": "reviewed",
    })
    await make_connection(ch3, material_prop)

    rollup = await get_action_items_by_property_graph(db_session)

    assert rollup["door/material"]["changes"] == 2


@pytest.mark.asyncio
async def test_graph_rollup_counts_pending_directives(
    db_session: AsyncSession, make_item, make_connection
):
    """Graph-based rollup counts only pending directives."""
    from app.services.dashboard_service import get_action_items_by_property_graph

    door = await make_item("door", "604", {"mark": "604"})
    width_prop, _ = await get_or_create_property_item(db_session, "door", "width")
    await ensure_property_connection(db_session, width_prop, door)

    # Create pending directive
    d1 = await make_item("directive", "604/width/pending", {
        "property_name": "width",
        "status": "pending",
    })
    await make_connection(d1, width_prop)

    # Create fulfilled directive (should not count)
    d2 = await make_item("directive", "604/width/fulfilled", {
        "property_name": "width",
        "status": "fulfilled",
    })
    await make_connection(d2, width_prop)

    rollup = await get_action_items_by_property_graph(db_session)

    assert rollup["door/width"]["directives"] == 1


@pytest.mark.asyncio
async def test_graph_rollup_empty_database(db_session: AsyncSession):
    """Graph-based rollup returns empty dict when no property items exist."""
    from app.services.dashboard_service import get_action_items_by_property_graph

    rollup = await get_action_items_by_property_graph(db_session)
    assert rollup == {}


@pytest.mark.asyncio
async def test_graph_rollup_multiple_properties_mixed_counts(
    db_session: AsyncSession, make_item, make_connection
):
    """Graph-based rollup correctly handles multiple properties with different counts."""
    from app.services.dashboard_service import get_action_items_by_property_graph

    door = await make_item("door", "605", {"mark": "605"})

    # Set up finish property with 2 conflicts
    finish_prop, _ = await get_or_create_property_item(db_session, "door", "finish")
    await ensure_property_connection(db_session, finish_prop, door)
    c1 = await make_item("conflict", "605/finish/1", {"status": "detected"})
    await make_connection(c1, finish_prop)
    c2 = await make_item("conflict", "605/finish/2", {"status": "detected"})
    await make_connection(c2, finish_prop)

    # Set up material property with 1 change + 1 directive
    material_prop, _ = await get_or_create_property_item(db_session, "door", "material")
    await ensure_property_connection(db_session, material_prop, door)
    ch = await make_item("change", "605/material/ch", {"status": "detected"})
    await make_connection(ch, material_prop)
    d = await make_item("directive", "605/material/d", {"status": "pending"})
    await make_connection(d, material_prop)

    rollup = await get_action_items_by_property_graph(db_session)

    assert rollup["door/finish"] == {"conflicts": 2, "changes": 0, "directives": 0}
    assert rollup["door/material"] == {"conflicts": 0, "changes": 1, "directives": 1}
