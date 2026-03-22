"""
Tests for WP-12a: Resolution Workflow + Directives API.

Covers:
  - Conflict resolution (chosen_source, manual_value)
  - Change acknowledgment
  - Directive fulfillment (manual)
  - Bulk resolution with partial failure
  - Action items rollup query
  - Directive listing with filters
  - Decision 8 compliance (resolution snapshot source)
  - Full workflow integration
"""

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Connection, Item, Snapshot


# ─── Fixtures ─────────────────────────────────────────────────

@pytest_asyncio.fixture
async def conflict_scenario(db_session: AsyncSession, make_item, make_connection):
    """
    Create a complete conflict scenario:
      - project, building, door (Door 101)
      - two sources: schedule, specification
      - milestone DD (ordinal 300)
      - conflicting snapshots: schedule says finish="paint", spec says finish="stain"
      - conflict item with 4 connections and self-sourced snapshot
    """
    # Project hierarchy
    project = await make_item("project", "Project Alpha", {"name": "Project Alpha"})
    building = await make_item("building", "Building A", {"name": "Building A"})
    await make_connection(project, building)

    # Door
    door = await make_item("door", "101", {"mark": "101"})
    await make_connection(building, door)

    # Sources
    schedule = await make_item("schedule", "Finish Schedule", {"name": "Finish Schedule"})
    spec = await make_item("specification", "Spec Section 09", {"name": "Spec Section 09"})
    await make_connection(project, schedule)
    await make_connection(project, spec)
    await make_connection(schedule, door)
    await make_connection(spec, door)

    # Milestone
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 300})
    await make_connection(project, dd)

    # Conflicting snapshots
    # Schedule says finish = "paint"
    schedule_snap = Snapshot(
        item_id=door.id, context_id=dd.id, source_id=schedule.id,
        properties={"finish": "paint", "material": "wood"},
    )
    db_session.add(schedule_snap)

    # Spec says finish = "stain"
    spec_snap = Snapshot(
        item_id=door.id, context_id=dd.id, source_id=spec.id,
        properties={"finish": "stain", "material": "wood"},
    )
    db_session.add(spec_snap)
    await db_session.flush()

    # Conflict item
    conflict = await make_item("conflict", "101 / finish", {
        "property_name": "finish",
        "status": "detected",
        "affected_item": str(door.id),
    })

    # Conflict self-sourced snapshot
    conflict_snap = Snapshot(
        item_id=conflict.id, context_id=dd.id, source_id=conflict.id,
        properties={
            "status": "DETECTED",
            "property_path": "finish",
            "values": {"Finish Schedule": "paint", "Spec Section 09": "stain"},
            "affected_item": str(door.id),
        },
    )
    db_session.add(conflict_snap)
    await db_session.flush()

    # 4 connections: conflict → door, schedule, spec, dd
    await make_connection(conflict, door)
    await make_connection(conflict, schedule)
    await make_connection(conflict, spec)
    await make_connection(conflict, dd)

    return {
        "project": project,
        "door": door,
        "schedule": schedule,
        "spec": spec,
        "dd": dd,
        "conflict": conflict,
    }


@pytest_asyncio.fixture
async def change_scenario(db_session: AsyncSession, make_item, make_connection):
    """
    Create a change scenario:
      - door, source, two milestones
      - change item detected between SD and DD
    """
    door = await make_item("door", "201", {"mark": "201"})
    schedule = await make_item("schedule", "Door Schedule", {"name": "Door Schedule"})
    sd = await make_item("milestone", "SD", {"name": "SD", "ordinal": 200})
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 300})
    await make_connection(schedule, door)

    # Snapshots at SD and DD
    db_session.add(Snapshot(
        item_id=door.id, context_id=sd.id, source_id=schedule.id,
        properties={"finish": "paint"},
    ))
    db_session.add(Snapshot(
        item_id=door.id, context_id=dd.id, source_id=schedule.id,
        properties={"finish": "stain"},
    ))
    await db_session.flush()

    # Change item
    change = await make_item("change", "Door Schedule / 201 / SD→DD", {
        "status": "DETECTED",
        "changes": {"finish": {"old": "paint", "new": "stain"}},
        "from_context": str(sd.id),
        "to_context": str(dd.id),
        "source": str(schedule.id),
        "affected_item": str(door.id),
        "property_name": "finish",
    })

    # Self-sourced snapshot
    db_session.add(Snapshot(
        item_id=change.id, context_id=dd.id, source_id=change.id,
        properties={
            "status": "DETECTED",
            "changes": {"finish": {"old": "paint", "new": "stain"}},
        },
    ))
    await db_session.flush()

    await make_connection(change, schedule)
    await make_connection(change, dd)
    await make_connection(change, sd)
    await make_connection(change, door)

    return {
        "door": door,
        "schedule": schedule,
        "sd": sd,
        "dd": dd,
        "change": change,
    }


# ─── Test: Resolve Conflict (Chosen Source) ───────────────────

@pytest.mark.asyncio
async def test_resolve_conflict_chosen_source(client, conflict_scenario):
    """POST /items/:conflict_id/resolve with chosen_source method."""
    s = conflict_scenario
    response = await client.post(
        f"/api/v1/items/{s['conflict'].id}/resolve",
        json={
            "chosen_value": "paint",
            "chosen_source_id": str(s["schedule"].id),
            "method": "chosen_source",
            "rationale": "Schedule is authoritative for finish",
            "decided_by": "Nick",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()

    # Decision item created
    assert data["decision_item"]["item_type"] == "decision"
    assert data["conflict_updated"] is True

    # Directive created for spec (the non-chosen source)
    assert data["directives_created"] >= 1

    # Verify conflict status updated
    conflict_resp = await client.get(f"/api/v1/items/{s['conflict'].id}")
    assert conflict_resp.status_code == 200
    assert conflict_resp.json()["properties"]["status"] == "resolved"


@pytest.mark.asyncio
async def test_resolve_conflict_manual_value(client, conflict_scenario):
    """POST /items/:conflict_id/resolve with manual_value method."""
    s = conflict_scenario
    response = await client.post(
        f"/api/v1/items/{s['conflict'].id}/resolve",
        json={
            "chosen_value": "lacquer",
            "method": "manual_value",
            "rationale": "Neither source is correct — lacquer per RFI",
            "decided_by": "Nick",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["decision_item"]["properties"]["resolved_value"] == "lacquer"
    # Both sources get directives (since neither had "lacquer")
    assert data["directives_created"] >= 2


@pytest.mark.asyncio
async def test_resolve_conflict_already_resolved(client, conflict_scenario):
    """Cannot resolve an already-resolved conflict."""
    s = conflict_scenario
    # Resolve first time
    await client.post(
        f"/api/v1/items/{s['conflict'].id}/resolve",
        json={
            "chosen_value": "paint",
            "chosen_source_id": str(s["schedule"].id),
            "method": "chosen_source",
            "rationale": "First resolution",
            "decided_by": "Nick",
        },
    )
    # Try again
    response = await client.post(
        f"/api/v1/items/{s['conflict'].id}/resolve",
        json={
            "chosen_value": "stain",
            "chosen_source_id": str(s["spec"].id),
            "method": "chosen_source",
            "rationale": "Second attempt",
            "decided_by": "Nick",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_resolve_conflict_not_found(client):
    """404 for nonexistent conflict."""
    fake_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/items/{fake_id}/resolve",
        json={
            "chosen_value": "paint",
            "method": "manual_value",
            "rationale": "test",
            "decided_by": "test",
        },
    )
    assert response.status_code == 404


# ─── Test: Decision 8 Compliance ─────────────────────────────

@pytest.mark.asyncio
async def test_decision_8_resolution_snapshot_source(client, db_session, conflict_scenario):
    """Resolution snapshot on conflict has source_id = decision_item_id."""
    s = conflict_scenario
    response = await client.post(
        f"/api/v1/items/{s['conflict'].id}/resolve",
        json={
            "chosen_value": "paint",
            "chosen_source_id": str(s["schedule"].id),
            "method": "chosen_source",
            "rationale": "Schedule wins",
            "decided_by": "Nick",
        },
    )
    data = response.json()
    decision_id = uuid.UUID(data["decision_item"]["id"])

    # Query snapshots on the conflict item
    result = await db_session.execute(
        select(Snapshot).where(Snapshot.item_id == s["conflict"].id)
    )
    conflict_snaps = result.scalars().all()

    # Should have at least 2: detection (source=conflict) and resolution (source=decision)
    assert len(conflict_snaps) >= 2

    # Find the resolution snapshot
    resolution_snaps = [
        snap for snap in conflict_snaps
        if snap.source_id == decision_id
    ]
    assert len(resolution_snaps) == 1, "Decision 8: resolution snapshot must have source_id = decision_id"

    res_snap = resolution_snaps[0]
    assert res_snap.properties["status"] == "resolved"
    assert res_snap.properties["resolved_value"] == "paint"


# ─── Test: Change Acknowledgment ─────────────────────────────

@pytest.mark.asyncio
async def test_acknowledge_change(client, change_scenario):
    """POST /items/:change_id/acknowledge updates status."""
    s = change_scenario
    response = await client.post(
        f"/api/v1/items/{s['change'].id}/acknowledge",
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["change_item_id"] == str(s["change"].id)
    assert data["status"] == "acknowledged"

    # Verify item updated
    item_resp = await client.get(f"/api/v1/items/{s['change'].id}")
    assert item_resp.json()["properties"]["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_acknowledge_change_idempotent(client, change_scenario):
    """Acknowledging twice is idempotent."""
    s = change_scenario
    await client.post(f"/api/v1/items/{s['change'].id}/acknowledge")
    response = await client.post(f"/api/v1/items/{s['change'].id}/acknowledge")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_acknowledge_change_not_found(client):
    """404 for nonexistent change."""
    fake_id = uuid.uuid4()
    response = await client.post(f"/api/v1/items/{fake_id}/acknowledge")
    assert response.status_code == 404


# ─── Test: Directive Fulfillment ─────────────────────────────

@pytest.mark.asyncio
async def test_fulfill_directive_manual(client, conflict_scenario):
    """Resolve conflict, then manually fulfill the created directive."""
    s = conflict_scenario
    # Resolve conflict → creates directive for spec
    resolve_resp = await client.post(
        f"/api/v1/items/{s['conflict'].id}/resolve",
        json={
            "chosen_value": "paint",
            "chosen_source_id": str(s["schedule"].id),
            "method": "chosen_source",
            "rationale": "Schedule is authoritative",
            "decided_by": "Nick",
        },
    )
    assert resolve_resp.status_code == 200

    # Get directives
    dir_resp = await client.get(f"/api/v1/directives?status=pending")
    assert dir_resp.status_code == 200
    directives = dir_resp.json()["directives"]
    assert len(directives) >= 1

    pending_directive = directives[0]
    directive_id = pending_directive["id"]

    # Fulfill it
    fulfill_resp = await client.post(f"/api/v1/items/{directive_id}/fulfill")
    assert fulfill_resp.status_code == 200
    assert fulfill_resp.json()["status"] == "fulfilled"

    # Verify it's now fulfilled
    dir_resp2 = await client.get(f"/api/v1/directives?status=pending")
    pending_after = [d for d in dir_resp2.json()["directives"]]
    assert len(pending_after) == 0


@pytest.mark.asyncio
async def test_fulfill_directive_idempotent(client, db_session, make_item, make_connection):
    """Fulfilling an already-fulfilled directive is idempotent."""
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 300})
    directive = await make_item("directive", "Test directive", {
        "property_name": "finish",
        "target_value": "paint",
        "target_source_id": str(uuid.uuid4()),
        "status": "fulfilled",
    })
    db_session.add(Snapshot(
        item_id=directive.id, context_id=dd.id, source_id=directive.id,
        properties={"status": "fulfilled"},
    ))
    await db_session.flush()

    response = await client.post(f"/api/v1/items/{directive.id}/fulfill")
    assert response.status_code == 200


# ─── Test: Bulk Resolution ───────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_resolve_success(client, db_session, make_item, make_connection):
    """Bulk resolve 2 conflicts successfully."""
    # Create 2 separate conflict scenarios
    door1 = await make_item("door", "301", {"mark": "301"})
    door2 = await make_item("door", "302", {"mark": "302"})
    schedule = await make_item("schedule", "Schedule", {"name": "Schedule"})
    spec = await make_item("specification", "Spec", {"name": "Spec"})
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 300})

    conflicts = []
    for door in [door1, door2]:
        # Snapshots
        db_session.add(Snapshot(
            item_id=door.id, context_id=dd.id, source_id=schedule.id,
            properties={"finish": "paint"},
        ))
        db_session.add(Snapshot(
            item_id=door.id, context_id=dd.id, source_id=spec.id,
            properties={"finish": "stain"},
        ))
        await db_session.flush()

        conflict = await make_item("conflict", f"{door.identifier} / finish", {
            "property_name": "finish",
            "status": "detected",
            "affected_item": str(door.id),
        })
        db_session.add(Snapshot(
            item_id=conflict.id, context_id=dd.id, source_id=conflict.id,
            properties={"status": "DETECTED"},
        ))
        await db_session.flush()

        await make_connection(conflict, door)
        await make_connection(conflict, schedule)
        await make_connection(conflict, spec)
        await make_connection(conflict, dd)
        conflicts.append(conflict)

    response = await client.post(
        "/api/v1/action-items/bulk-resolve",
        json={
            "resolutions": [
                {
                    "conflict_item_id": str(c.id),
                    "chosen_value": "paint",
                    "chosen_source_id": str(schedule.id),
                    "method": "chosen_source",
                    "rationale": "Bulk resolve",
                    "decided_by": "Nick",
                }
                for c in conflicts
            ],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_attempted"] == 2
    assert data["total_succeeded"] == 2
    assert data["total_failed"] == 0


@pytest.mark.asyncio
async def test_bulk_resolve_partial_failure(client, db_session, make_item, make_connection):
    """Bulk resolve with 1 valid + 1 invalid conflict → partial success."""
    door = await make_item("door", "401", {"mark": "401"})
    schedule = await make_item("schedule", "Schedule", {"name": "Schedule"})
    spec = await make_item("specification", "Spec", {"name": "Spec"})
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 300})

    db_session.add(Snapshot(
        item_id=door.id, context_id=dd.id, source_id=schedule.id,
        properties={"finish": "paint"},
    ))
    db_session.add(Snapshot(
        item_id=door.id, context_id=dd.id, source_id=spec.id,
        properties={"finish": "stain"},
    ))
    await db_session.flush()

    conflict = await make_item("conflict", "401 / finish", {
        "property_name": "finish",
        "status": "detected",
        "affected_item": str(door.id),
    })
    db_session.add(Snapshot(
        item_id=conflict.id, context_id=dd.id, source_id=conflict.id,
        properties={"status": "DETECTED"},
    ))
    await db_session.flush()
    await make_connection(conflict, door)
    await make_connection(conflict, schedule)
    await make_connection(conflict, spec)
    await make_connection(conflict, dd)

    fake_conflict_id = uuid.uuid4()
    response = await client.post(
        "/api/v1/action-items/bulk-resolve",
        json={
            "resolutions": [
                {
                    "conflict_item_id": str(conflict.id),
                    "chosen_value": "paint",
                    "chosen_source_id": str(schedule.id),
                    "method": "chosen_source",
                    "rationale": "Valid",
                    "decided_by": "Nick",
                },
                {
                    "conflict_item_id": str(fake_conflict_id),
                    "chosen_value": "stain",
                    "method": "manual_value",
                    "rationale": "Invalid",
                    "decided_by": "Nick",
                },
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_succeeded"] == 1
    assert data["total_failed"] == 1

    # Find the failed result
    failed = [r for r in data["results"] if not r["success"]]
    assert len(failed) == 1
    assert "not found" in failed[0]["error"].lower()


# ─── Test: Action Items Rollup ───────────────────────────────

@pytest.mark.asyncio
async def test_action_items_rollup(client, conflict_scenario, change_scenario):
    """GET /action-items returns correct counts."""
    response = await client.get("/api/v1/action-items")
    assert response.status_code == 200
    data = response.json()

    # Should have at least 1 conflict (from conflict_scenario) and 1 change (from change_scenario)
    assert data["conflicts_pending"] >= 1
    assert data["changes_pending"] >= 1
    assert data["total_action_items"] >= 2


@pytest.mark.asyncio
async def test_action_items_after_resolve(client, conflict_scenario):
    """After resolving a conflict, rollup changes."""
    s = conflict_scenario

    # Before: 1 conflict pending
    before = await client.get("/api/v1/action-items")
    assert before.json()["conflicts_pending"] >= 1

    # Resolve
    await client.post(
        f"/api/v1/items/{s['conflict'].id}/resolve",
        json={
            "chosen_value": "paint",
            "chosen_source_id": str(s["schedule"].id),
            "method": "chosen_source",
            "rationale": "test",
            "decided_by": "Nick",
        },
    )

    # After: conflict resolved, but directive pending
    after = await client.get("/api/v1/action-items")
    after_data = after.json()
    assert after_data["conflicts_pending"] == 0
    assert after_data["directives_pending"] >= 1


# ─── Test: Directive Listing ─────────────────────────────────

@pytest.mark.asyncio
async def test_list_directives_filter_by_source(client, conflict_scenario):
    """GET /directives?source_id=X returns directives for that source."""
    s = conflict_scenario

    # Resolve to create directives
    await client.post(
        f"/api/v1/items/{s['conflict'].id}/resolve",
        json={
            "chosen_value": "paint",
            "chosen_source_id": str(s["schedule"].id),
            "method": "chosen_source",
            "rationale": "test",
            "decided_by": "Nick",
        },
    )

    # Filter by spec (the non-chosen source)
    resp = await client.get(f"/api/v1/directives?source_id={s['spec'].id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    # All returned directives should target the spec
    for d in data["directives"]:
        assert d["target_source_id"] == str(s["spec"].id)

    # Filter by schedule (chosen source) — should return 0
    resp2 = await client.get(f"/api/v1/directives?source_id={s['schedule'].id}")
    assert resp2.json()["total"] == 0
