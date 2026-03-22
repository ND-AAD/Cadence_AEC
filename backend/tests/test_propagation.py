"""
Tests for WP-18: Specification Propagation.

Covers:
  - propagate_extractions: creates section and element snapshots
  - source_id = spec_section (Decision D-21)
  - Conflict detection runs on propagated values
  - Directive fulfillment runs on propagated values
  - Conditional assertions deferred with needs_assignment
  - assign_conditional_values: resolves conditionals
  - Batch status transitions: confirmed → propagated
  - Error cases: missing batch, wrong status, already propagated
  - API routes: POST /propagate, GET /assignments, POST /assign
"""

import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Connection, Item, Snapshot
from app.services.propagation_service import (
    PropagationResult,
    propagate_extractions,
    get_pending_assignments,
    assign_conditional_values,
)


# ─── Helpers ──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def propagation_setup(make_item, make_connection, db_session):
    """
    Set up a confirmed extraction batch with:
    - Project, spec, milestone
    - spec_section with section_item_id
    - 2 door items (Door 101, Door 102)
    - extraction_results with one noun (door) and flat extractions
    """
    project = await make_item("project", "Project Alpha")
    spec = await make_item("specification", "Project Spec", {"discipline": "Architectural"})
    milestone = await make_item("milestone", "DD", {"name": "DD", "ordinal": 100})
    await make_connection(project, spec)
    await make_connection(project, milestone)

    # Spec section
    section = await make_item("spec_section", "08 11 13", {
        "title": "Hollow Metal Doors and Frames",
        "division": "08",
    })
    await make_connection(spec, section)

    # Elements
    door1 = await make_item("door", "Door 101", {"mark": "101"})
    door2 = await make_item("door", "Door 102", {"mark": "102"})

    # Preprocess batch (parent)
    preprocess = await make_item("preprocess_batch", "PP-1", {
        "status": "completed",
        "spec_item_id": str(spec.id),
    })

    # Extraction batch — confirmed
    batch = await make_item("extraction_batch", "EX-1", {
        "status": "confirmed",
        "milestone_id": str(milestone.id),
        "preprocess_batch_id": str(preprocess.id),
        "extraction_results": {
            "sections": {
                "08 11 13": {
                    "status": "extracted",
                    "section_item_id": str(section.id),
                    "nouns": [
                        {
                            "noun_phrase": "hollow metal door",
                            "matched_type": "door",
                            "attribution_status": "matched",
                            "attributed_elements": [
                                str(door1.id),
                                str(door2.id),
                            ],
                            "extractions": [
                                {
                                    "property_name": "material",
                                    "value": "hollow metal",
                                    "assertion_type": "flat",
                                },
                                {
                                    "property_name": "finish",
                                    "value": "prime coat",
                                    "assertion_type": "flat",
                                },
                            ],
                        },
                    ],
                },
            },
        },
    })

    return {
        "project": project,
        "spec": spec,
        "milestone": milestone,
        "section": section,
        "door1": door1,
        "door2": door2,
        "batch": batch,
        "preprocess": preprocess,
    }


@pytest_asyncio.fixture
async def conditional_setup(make_item, make_connection, db_session):
    """
    Same as propagation_setup but with a conditional assertion.
    """
    project = await make_item("project", "Project Beta")
    spec = await make_item("specification", "Project Spec B")
    milestone = await make_item("milestone", "DD", {"name": "DD", "ordinal": 100})

    section = await make_item("spec_section", "08 71 00", {
        "title": "Door Hardware",
        "division": "08",
    })
    await make_connection(spec, section)

    door1 = await make_item("door", "Door 201")
    door2 = await make_item("door", "Door 202")

    preprocess = await make_item("preprocess_batch", "PP-2", {
        "status": "completed",
        "spec_item_id": str(spec.id),
    })

    batch = await make_item("extraction_batch", "EX-2", {
        "status": "confirmed",
        "milestone_id": str(milestone.id),
        "preprocess_batch_id": str(preprocess.id),
        "extraction_results": {
            "sections": {
                "08 71 00": {
                    "status": "extracted",
                    "section_item_id": str(section.id),
                    "nouns": [
                        {
                            "noun_phrase": "door",
                            "matched_type": "door",
                            "attribution_status": "matched",
                            "attributed_elements": [
                                str(door1.id),
                                str(door2.id),
                            ],
                            "extractions": [
                                {
                                    "property_name": "hardware_set",
                                    "assertion_type": "conditional",
                                    "assertions": [
                                        {"value": "HW-1", "condition": "exterior"},
                                        {"value": "HW-2", "condition": "interior"},
                                    ],
                                },
                                {
                                    "property_name": "closer",
                                    "value": "LCN 4041",
                                    "assertion_type": "flat",
                                },
                            ],
                        },
                    ],
                },
            },
        },
    })

    return {
        "project": project,
        "spec": spec,
        "milestone": milestone,
        "section": section,
        "door1": door1,
        "door2": door2,
        "batch": batch,
    }


# ─── Tests: Core Propagation ─────────────────────────────────


@pytest.mark.asyncio
async def test_propagation_creates_element_snapshots(propagation_setup, db_session):
    """Propagation creates element-level snapshots for attributed elements."""
    setup = propagation_setup
    result = await propagate_extractions(db_session, setup["batch"].id)

    assert result.element_snapshots_created == 2  # door1 and door2

    # Verify snapshot for door1
    snap_result = await db_session.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == setup["door1"].id,
                Snapshot.context_id == setup["milestone"].id,
                Snapshot.source_id == setup["section"].id,  # D-21
            )
        )
    )
    snap = snap_result.scalar_one()
    assert snap.properties["material"] == "hollow metal"
    assert snap.properties["finish"] == "prime coat"


@pytest.mark.asyncio
async def test_propagation_source_is_spec_section(propagation_setup, db_session):
    """Decision D-21: source_id = spec_section item, not spec document."""
    setup = propagation_setup
    await propagate_extractions(db_session, setup["batch"].id)

    snap_result = await db_session.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == setup["door1"].id,
                Snapshot.context_id == setup["milestone"].id,
            )
        )
    )
    snap = snap_result.scalar_one()
    assert snap.source_id == setup["section"].id  # NOT spec.id


@pytest.mark.asyncio
async def test_propagation_creates_section_snapshot(propagation_setup, db_session):
    """Propagation creates a section self-sourced snapshot."""
    setup = propagation_setup
    result = await propagate_extractions(db_session, setup["batch"].id)

    assert result.section_snapshots_created == 1

    snap_result = await db_session.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == setup["section"].id,
                Snapshot.context_id == setup["milestone"].id,
                Snapshot.source_id == setup["section"].id,  # self-sourced
            )
        )
    )
    snap = snap_result.scalar_one()
    assert "material" in snap.properties
    assert "finish" in snap.properties


@pytest.mark.asyncio
async def test_propagation_creates_connections(propagation_setup, db_session):
    """Propagation creates spec_section → element connections."""
    setup = propagation_setup
    await propagate_extractions(db_session, setup["batch"].id)

    conn_result = await db_session.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id == setup["section"].id,
                Connection.target_item_id == setup["door1"].id,
            )
        )
    )
    conn = conn_result.scalar_one()
    assert conn.properties.get("relationship") == "spec_governs"


@pytest.mark.asyncio
async def test_propagation_updates_batch_status(propagation_setup, db_session):
    """Batch status transitions to 'propagated'."""
    setup = propagation_setup
    await propagate_extractions(db_session, setup["batch"].id)

    await db_session.refresh(setup["batch"])
    assert setup["batch"].properties["status"] == "propagated"


@pytest.mark.asyncio
async def test_propagation_idempotent_upsert(propagation_setup, db_session):
    """Re-propagating updates existing snapshots rather than creating duplicates."""
    setup = propagation_setup

    # First propagation
    result1 = await propagate_extractions(db_session, setup["batch"].id)
    assert result1.element_snapshots_created == 2

    # Reset batch to confirmed for re-propagation test
    setup["batch"].properties = {**setup["batch"].properties, "status": "confirmed"}
    await db_session.flush()

    # Second propagation
    result2 = await propagate_extractions(db_session, setup["batch"].id)
    assert result2.element_snapshots_updated == 2
    assert result2.element_snapshots_created == 0


# ─── Tests: Conflict Detection on Propagation ────────────────


@pytest.mark.asyncio
async def test_propagation_detects_conflicts(propagation_setup, db_session, make_item):
    """If schedule says material=wood and spec says material=hollow metal → conflict."""
    setup = propagation_setup

    # Create a schedule source with a conflicting snapshot
    schedule = await make_item("schedule", "Finish Schedule", {"discipline": "Architectural"})
    db_session.add(Snapshot(
        item_id=setup["door1"].id,
        context_id=setup["milestone"].id,
        source_id=schedule.id,
        properties={"material": "wood"},  # Disagrees with spec's "hollow metal"
    ))
    await db_session.flush()

    result = await propagate_extractions(db_session, setup["batch"].id)

    assert result.conflicts_detected >= 1

    # Verify conflict item exists
    conflict_result = await db_session.execute(
        select(Item).where(Item.item_type == "conflict")
    )
    conflicts = conflict_result.scalars().all()
    material_conflicts = [c for c in conflicts if "material" in (c.identifier or "")]
    assert len(material_conflicts) >= 1


@pytest.mark.asyncio
async def test_propagation_no_conflict_on_agreement(propagation_setup, db_session, make_item):
    """If schedule and spec agree on material → no conflict."""
    setup = propagation_setup

    schedule = await make_item("schedule", "Finish Schedule", {"discipline": "Architectural"})
    db_session.add(Snapshot(
        item_id=setup["door1"].id,
        context_id=setup["milestone"].id,
        source_id=schedule.id,
        properties={"material": "hollow metal"},  # Agrees with spec
    ))
    await db_session.flush()

    result = await propagate_extractions(db_session, setup["batch"].id)

    assert result.conflicts_detected == 0


# ─── Tests: Directive Fulfillment on Propagation ─────────────


@pytest.mark.asyncio
async def test_propagation_fulfills_directives(propagation_setup, db_session, make_item):
    """Spec propagation fulfills directive targeting the spec section."""
    setup = propagation_setup

    # Create directive targeting spec section for door1 material
    directive = await make_item("directive", "Dir: Door 101 / material", {
        "property_name": "material",
        "target_value": "hollow metal",
        "target_source_id": str(setup["section"].id),  # Targets spec section
        "affected_item_id": str(setup["door1"].id),
        "status": "pending",
    })
    # Self-sourced snapshot
    db_session.add(Snapshot(
        item_id=directive.id,
        context_id=setup["milestone"].id,
        source_id=directive.id,
        properties={"status": "pending", "target_value": "hollow metal"},
    ))
    await db_session.flush()

    result = await propagate_extractions(db_session, setup["batch"].id)

    assert result.directives_fulfilled >= 1

    await db_session.refresh(directive)
    assert directive.properties["status"] == "fulfilled"


# ─── Tests: Conditional Assertions ───────────────────────────


@pytest.mark.asyncio
async def test_conditional_deferred(conditional_setup, db_session):
    """Conditional assertions are propagated with needs_assignment=True."""
    setup = conditional_setup
    result = await propagate_extractions(db_session, setup["batch"].id)

    assert result.conditionals_deferred >= 1

    # Check element snapshot has conditional structure
    snap_result = await db_session.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == setup["door1"].id,
                Snapshot.context_id == setup["milestone"].id,
                Snapshot.source_id == setup["section"].id,
            )
        )
    )
    snap = snap_result.scalar_one()
    hw_prop = snap.properties.get("hardware_set")
    assert isinstance(hw_prop, dict)
    assert hw_prop["_conditional"] is True
    assert hw_prop["_needs_assignment"] is True
    assert len(hw_prop["assertions"]) == 2

    # Flat property should still be concrete
    assert snap.properties["closer"] == "LCN 4041"


@pytest.mark.asyncio
async def test_assign_conditional_values(conditional_setup, db_session):
    """assign_conditional_values replaces conditional with concrete value."""
    setup = conditional_setup
    await propagate_extractions(db_session, setup["batch"].id)

    result = await assign_conditional_values(
        db_session,
        [{
            "element_ids": [str(setup["door1"].id)],
            "property_name": "hardware_set",
            "value": "HW-1",
            "source_condition": "exterior",
            "section_item_id": str(setup["section"].id),
        }],
        setup["batch"].id,
    )

    assert result["assignments_made"] == 1

    # Verify snapshot updated to concrete value
    snap_result = await db_session.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == setup["door1"].id,
                Snapshot.source_id == setup["section"].id,
            )
        )
    )
    snap = snap_result.scalar_one()
    assert snap.properties["hardware_set"] == "HW-1"


# ─── Tests: Error Cases ──────────────────────────────────────


@pytest.mark.asyncio
async def test_propagation_rejects_wrong_status(make_item, db_session):
    """Batch must be in 'confirmed' status to propagate."""
    milestone = await make_item("milestone", "DD", {"ordinal": 100})
    batch = await make_item("extraction_batch", "EX-bad", {
        "status": "processing",
        "milestone_id": str(milestone.id),
    })

    with pytest.raises(ValueError, match="must be in 'confirmed' status"):
        await propagate_extractions(db_session, batch.id)


@pytest.mark.asyncio
async def test_propagation_rejects_already_propagated(propagation_setup, db_session):
    """Already propagated batch cannot be propagated again."""
    setup = propagation_setup
    await propagate_extractions(db_session, setup["batch"].id)

    with pytest.raises(ValueError, match="already propagated"):
        await propagate_extractions(db_session, setup["batch"].id)


@pytest.mark.asyncio
async def test_propagation_rejects_missing_batch(db_session):
    """Non-existent batch raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        await propagate_extractions(db_session, uuid.uuid4())


# ─── Tests: API Routes ──────────────────────────────────────


@pytest.mark.asyncio
async def test_propagate_api_endpoint(client: AsyncClient, propagation_setup):
    """POST /api/v1/spec/propagate creates snapshots and returns summary."""
    setup = propagation_setup

    resp = await client.post(
        "/api/v1/spec/propagate",
        json={"batch_id": str(setup["batch"].id)},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["summary"]["element_snapshots_created"] == 2
    assert data["summary"]["section_snapshots_created"] == 1
    assert data["summary"]["status"] == "propagated"


@pytest.mark.asyncio
async def test_propagate_api_rejects_bad_status(client: AsyncClient, make_item):
    """POST /api/v1/spec/propagate returns 400 for wrong status."""
    milestone = await make_item("milestone", "DD", {"ordinal": 100})
    batch = await make_item("extraction_batch", "EX-bad", {
        "status": "processing",
        "milestone_id": str(milestone.id),
    })

    resp = await client.post(
        "/api/v1/spec/propagate",
        json={"batch_id": str(batch.id)},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_assign_conditionals_api_endpoint(
    client: AsyncClient, conditional_setup,
):
    """POST /api/v1/spec/propagate/assign resolves conditionals."""
    setup = conditional_setup

    # First propagate
    resp = await client.post(
        "/api/v1/spec/propagate",
        json={"batch_id": str(setup["batch"].id)},
    )
    assert resp.status_code == 201

    # Then assign
    resp2 = await client.post(
        "/api/v1/spec/propagate/assign",
        json={
            "batch_id": str(setup["batch"].id),
            "assignments": [
                {
                    "element_ids": [str(setup["door1"].id)],
                    "property_name": "hardware_set",
                    "value": "HW-1",
                    "source_condition": "exterior",
                    "section_item_id": str(setup["section"].id),
                },
            ],
        },
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["assignments_made"] == 1
