"""
Tests for WP-11: Conflict Detection on Import.

Covers:
  - Conflict detection when two sources disagree on a property
  - No false conflicts (normalized comparison)
  - Single_source properties don't trigger conflicts
  - Auto-resolution when sources come into agreement
  - Conflict items have correct connections (4: affected, both sources, milestone)
  - One conflict per property per item (Decision 5)
  - Import summary counts (new_conflicts, resolved_conflicts)
"""

import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Connection, Item, Snapshot
from tests.fixtures.excel_factory import (
    STANDARD_DOOR_MAPPING,
    make_door_schedule_excel,
    make_updated_door_schedule_excel,
)


# ─── Helpers ──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def project_setup(make_item, make_connection):
    """Create project with schedule, spec, and milestones."""
    project = await make_item("project", "Project Alpha")
    schedule = await make_item(
        "schedule", "Finish Schedule",
        {"name": "Finish Schedule", "discipline": "Architectural"},
    )
    spec = await make_item(
        "specification", "Door Spec",
        {"name": "Door Specification", "discipline": "Architectural"},
    )
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 100})
    cd = await make_item("milestone", "CD", {"name": "CD", "ordinal": 200})

    await make_connection(project, schedule)
    await make_connection(project, spec)
    await make_connection(project, dd)
    await make_connection(project, cd)

    return {
        "project": project,
        "schedule": schedule,
        "spec": spec,
        "dd_milestone": dd,
        "cd_milestone": cd,
    }


def _make_spec_excel(doors: list[dict]) -> bytes:
    """Build a custom Excel file for spec import."""
    import io
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DOOR NO.", "WIDTH", "HEIGHT", "FINISH", "MATERIAL", "HARDWARE SET", "FIRE RATING"])
    for d in doors:
        ws.append([
            d.get("id", "Door 001"),
            d.get("width", "3'-0\""),
            d.get("height", "7'-0\""),
            d.get("finish", "paint"),
            d.get("material", "wood"),
            d.get("hardware_set", "HW-1"),
            d.get("fire_rating", ""),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ─── Tests: Conflict Detection ────────────────────────────────


@pytest.mark.asyncio
async def test_no_conflicts_when_sources_agree(client: AsyncClient, project_setup):
    """Two sources with same values → no conflicts."""
    setup = project_setup

    # Import schedule with finish=paint for Door 001
    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                     "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )

    # Import spec with same finish=paint
    spec_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                    "hardware_set": "HW-1", "fire_rating": ""}])
    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )
    assert resp.status_code == 201
    result = resp.json()
    assert result["summary"]["new_conflicts"] == 0


@pytest.mark.asyncio
async def test_conflict_detected_when_sources_disagree(client: AsyncClient, project_setup):
    """Two sources disagree on finish → conflict created."""
    setup = project_setup

    # Schedule says finish=paint
    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                     "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )

    # Spec says finish=stain (different!)
    spec_data = _make_spec_excel([{"id": "Door 001", "finish": "stain", "material": "wood",
                                    "hardware_set": "HW-1", "fire_rating": ""}])
    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )
    assert resp.status_code == 201
    result = resp.json()
    assert result["summary"]["new_conflicts"] >= 1

    # At least one conflict for finish
    finish_conflicts = [c for c in result["conflict_items"] if c["property_name"] == "finish"]
    assert len(finish_conflicts) >= 1
    conflict = finish_conflicts[0]
    assert "paint" in conflict["values"].values() or "stain" in conflict["values"].values()


@pytest.mark.asyncio
async def test_normalized_comparison_prevents_false_conflict(client: AsyncClient, project_setup):
    """'Paint' vs 'paint' should NOT create a conflict (case-insensitive)."""
    setup = project_setup

    # Schedule says finish=paint
    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                     "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )

    # Spec says finish=Paint (different case only)
    spec_data = _make_spec_excel([{"id": "Door 001", "finish": "Paint", "material": "wood",
                                    "hardware_set": "HW-1", "fire_rating": ""}])
    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )
    assert resp.status_code == 201
    result = resp.json()
    # No conflict on finish (case insensitive)
    finish_conflicts = [c for c in result["conflict_items"] if c["property_name"] == "finish"]
    assert len(finish_conflicts) == 0


@pytest.mark.asyncio
async def test_single_source_no_conflict(client: AsyncClient, project_setup):
    """Properties only reported by one source don't create conflicts."""
    setup = project_setup

    # Only import from schedule (no spec import)
    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint"}])
    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )
    assert resp.status_code == 201
    result = resp.json()
    assert result["summary"]["new_conflicts"] == 0


@pytest.mark.asyncio
async def test_conflict_item_has_correct_identifier(
    client: AsyncClient, project_setup, db_session
):
    """Conflict item identifier: '{item} / {property}'."""
    setup = project_setup

    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                     "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )

    spec_data = _make_spec_excel([{"id": "Door 001", "finish": "stain", "material": "wood",
                                    "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )

    result = await db_session.execute(
        select(Item).where(Item.item_type == "conflict")
    )
    conflicts = result.scalars().all()
    assert len(conflicts) >= 1

    finish_conflict = [c for c in conflicts if "finish" in c.identifier]
    assert len(finish_conflict) == 1
    assert finish_conflict[0].identifier == "Door 001 / finish"


@pytest.mark.asyncio
async def test_conflict_item_has_connections(
    client: AsyncClient, project_setup, db_session
):
    """Conflict item connected to affected item, both sources, and milestone."""
    setup = project_setup

    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                     "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )

    spec_data = _make_spec_excel([{"id": "Door 001", "finish": "stain", "material": "wood",
                                    "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )

    # Find the conflict item
    conflict_result = await db_session.execute(
        select(Item).where(
            and_(Item.item_type == "conflict", Item.identifier == "Door 001 / finish")
        )
    )
    conflict = conflict_result.scalar_one()

    # Check connections
    conn_result = await db_session.execute(
        select(Connection).where(Connection.source_item_id == conflict.id)
    )
    conns = conn_result.scalars().all()
    target_ids = {c.target_item_id for c in conns}

    # Should be connected to: affected item (Door 001), schedule, spec, milestone
    assert setup["schedule"].id in target_ids
    assert setup["spec"].id in target_ids
    assert setup["dd_milestone"].id in target_ids
    assert len(target_ids) >= 4  # at least those 4


@pytest.mark.asyncio
async def test_conflict_has_self_sourced_snapshot(
    client: AsyncClient, project_setup, db_session
):
    """Conflict item has a self-sourced snapshot with DETECTED status."""
    setup = project_setup

    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                     "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )

    spec_data = _make_spec_excel([{"id": "Door 001", "finish": "stain", "material": "wood",
                                    "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )

    # Find conflict
    conflict_result = await db_session.execute(
        select(Item).where(Item.identifier == "Door 001 / finish")
    )
    conflict = conflict_result.scalar_one()

    # Check self-sourced snapshot
    snap_result = await db_session.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == conflict.id,
                Snapshot.source_id == conflict.id,
            )
        )
    )
    snap = snap_result.scalar_one()
    assert snap.properties["status"] == "DETECTED"
    assert snap.properties["property_path"] == "finish"
    assert "values" in snap.properties


@pytest.mark.asyncio
async def test_one_conflict_per_property_per_item(
    client: AsyncClient, project_setup, db_session
):
    """Decision 5: one conflict per property per item, not one per source pair."""
    setup = project_setup

    # Two disagreeing properties (finish and material)
    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                     "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )

    spec_data = _make_spec_excel([{"id": "Door 001", "finish": "stain", "material": "steel",
                                    "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )

    # Should have 2 conflict items: one for finish, one for material
    result = await db_session.execute(
        select(Item).where(Item.item_type == "conflict")
    )
    conflicts = result.scalars().all()
    assert len(conflicts) == 2
    identifiers = {c.identifier for c in conflicts}
    assert "Door 001 / finish" in identifiers
    assert "Door 001 / material" in identifiers


@pytest.mark.asyncio
async def test_auto_resolution_when_sources_agree(client: AsyncClient, project_setup, db_session):
    """
    If sources come into agreement on a previously conflicted property,
    the conflict is auto-resolved.
    """
    setup = project_setup

    # Step 1: Create conflict at DD
    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                     "hardware_set": "HW-1", "fire_rating": ""}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )
    spec_data = _make_spec_excel([{"id": "Door 001", "finish": "stain", "material": "wood",
                                    "hardware_set": "HW-1", "fire_rating": ""}])
    resp1 = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )
    assert resp1.json()["summary"]["new_conflicts"] >= 1

    # Step 2: Schedule now agrees at CD (changes to "stain")
    sched_updated = _make_spec_excel([{"id": "Door 001", "finish": "stain", "material": "wood",
                                        "hardware_set": "HW-1", "fire_rating": ""}])
    resp2 = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["cd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_updated, "application/octet-stream")},
    )
    assert resp2.status_code == 201
    result2 = resp2.json()
    assert result2["summary"]["resolved_conflicts"] >= 1

    # Verify conflict item status is updated
    conflict_result = await db_session.execute(
        select(Item).where(Item.identifier == "Door 001 / finish")
    )
    conflict = conflict_result.scalar_one()
    assert conflict.properties["status"] == "resolved_by_agreement"


@pytest.mark.asyncio
async def test_multiple_doors_conflict_count(client: AsyncClient, project_setup):
    """Import 5 doors where 3 have different finish → 3 conflicts."""
    setup = project_setup

    # Schedule: all doors with finish=paint
    sched_doors = [
        {"id": f"Door {i:03d}", "finish": "paint", "material": "wood",
         "hardware_set": "HW-1", "fire_rating": ""}
        for i in range(1, 6)
    ]
    sched_data = _make_spec_excel(sched_doors)
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )

    # Spec: doors 1-3 have finish=stain (conflict), doors 4-5 have finish=paint (agree)
    spec_doors = [
        {"id": f"Door {i:03d}",
         "finish": "stain" if i <= 3 else "paint",
         "material": "wood", "hardware_set": "HW-1", "fire_rating": ""}
        for i in range(1, 6)
    ]
    spec_data = _make_spec_excel(spec_doors)
    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )
    assert resp.status_code == 201
    result = resp.json()
    assert result["summary"]["new_conflicts"] == 3


@pytest.mark.asyncio
async def test_conflict_property_only_when_both_sources_have_value(
    client: AsyncClient, project_setup
):
    """If other source doesn't address a property, no conflict for that property."""
    setup = project_setup

    # Schedule has fire_rating=""
    sched_data = _make_spec_excel([{"id": "Door 001", "finish": "paint", "material": "wood",
                                     "hardware_set": "HW-1", "fire_rating": "60 min"}])
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", sched_data, "application/octet-stream")},
    )

    # Spec has finish=stain but no fire_rating (empty = not present)
    # fire_rating won't conflict because empty string comparison
    spec_data = _make_spec_excel([{"id": "Door 001", "finish": "stain", "material": "wood",
                                    "hardware_set": "HW-1", "fire_rating": ""}])
    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["spec"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("spec.xlsx", spec_data, "application/octet-stream")},
    )
    assert resp.status_code == 201
    result = resp.json()
    # finish should conflict, fire_rating should not since spec has empty
    finish_conflicts = [c for c in result["conflict_items"] if c["property_name"] == "finish"]
    assert len(finish_conflicts) >= 1
