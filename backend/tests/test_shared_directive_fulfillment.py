"""
Tests for shared directive_fulfillment module — WP-18.0.

Covers:
  - check_directive_fulfillment: matching values auto-fulfill
  - Non-matching values leave directives pending
  - Only directives targeting the correct source+item are checked
  - Batch fulfillment across multiple items
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Item, Snapshot
from app.services.directive_fulfillment import (
    check_directive_fulfillment,
    check_directive_fulfillment_batch,
)


# ─── Helpers ──────────────────────────────────────────────────


async def _make_directive(
    db_session, make_item,
    affected_item_id: uuid.UUID,
    target_source_id: uuid.UUID,
    property_name: str,
    target_value: str,
    status: str = "pending",
) -> Item:
    """Create a directive item with self-sourced snapshot."""
    milestone = await make_item("milestone", f"M-{uuid.uuid4().hex[:6]}", {"ordinal": 100})
    directive = await make_item(
        "directive",
        f"Directive: test / {property_name}",
        {
            "property_name": property_name,
            "target_value": target_value,
            "target_source_id": str(target_source_id),
            "affected_item_id": str(affected_item_id),
            "status": status,
        },
    )
    db_session.add(Snapshot(
        item_id=directive.id,
        context_id=milestone.id,
        source_id=directive.id,
        properties={
            "property_name": property_name,
            "target_value": target_value,
            "target_source_id": str(target_source_id),
            "status": status,
        },
    ))
    await db_session.flush()
    return directive


# ─── check_directive_fulfillment ──────────────────────────────


@pytest.mark.asyncio
async def test_fulfillment_on_matching_value(make_item, db_session):
    """Directive is fulfilled when imported value matches target."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")

    directive = await _make_directive(
        db_session, make_item,
        affected_item_id=door.id,
        target_source_id=schedule.id,
        property_name="finish",
        target_value="stain",
    )

    count = await check_directive_fulfillment(
        db_session, schedule.id, door.id, {"finish": "stain"}
    )

    assert count == 1
    await db_session.refresh(directive)
    assert directive.properties["status"] == "fulfilled"


@pytest.mark.asyncio
async def test_no_fulfillment_on_non_matching_value(make_item, db_session):
    """Directive stays pending when values don't match."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")

    directive = await _make_directive(
        db_session, make_item,
        affected_item_id=door.id,
        target_source_id=schedule.id,
        property_name="finish",
        target_value="stain",
    )

    count = await check_directive_fulfillment(
        db_session, schedule.id, door.id, {"finish": "paint"}
    )

    assert count == 0
    await db_session.refresh(directive)
    assert directive.properties["status"] == "pending"


@pytest.mark.asyncio
async def test_no_fulfillment_wrong_source(make_item, db_session):
    """Directive targeting a different source is not affected."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")
    spec = await make_item("specification", "Spec B")

    directive = await _make_directive(
        db_session, make_item,
        affected_item_id=door.id,
        target_source_id=schedule.id,  # Targets schedule
        property_name="finish",
        target_value="stain",
    )

    # Import from spec (not schedule) → no fulfillment
    count = await check_directive_fulfillment(
        db_session, spec.id, door.id, {"finish": "stain"}
    )

    assert count == 0
    await db_session.refresh(directive)
    assert directive.properties["status"] == "pending"


@pytest.mark.asyncio
async def test_no_fulfillment_wrong_item(make_item, db_session):
    """Directive targeting a different item is not affected."""
    door1 = await make_item("door", "Door 101")
    door2 = await make_item("door", "Door 102")
    schedule = await make_item("schedule", "Schedule A")

    directive = await _make_directive(
        db_session, make_item,
        affected_item_id=door1.id,  # Targets door1
        target_source_id=schedule.id,
        property_name="finish",
        target_value="stain",
    )

    # Import for door2 (not door1) → no fulfillment
    count = await check_directive_fulfillment(
        db_session, schedule.id, door2.id, {"finish": "stain"}
    )

    assert count == 0
    await db_session.refresh(directive)
    assert directive.properties["status"] == "pending"


@pytest.mark.asyncio
async def test_already_fulfilled_not_counted(make_item, db_session):
    """Already fulfilled directives are skipped."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")

    await _make_directive(
        db_session, make_item,
        affected_item_id=door.id,
        target_source_id=schedule.id,
        property_name="finish",
        target_value="stain",
        status="fulfilled",
    )

    count = await check_directive_fulfillment(
        db_session, schedule.id, door.id, {"finish": "stain"}
    )
    assert count == 0


@pytest.mark.asyncio
async def test_snapshot_updated_on_fulfillment(make_item, db_session):
    """Directive's self-sourced snapshot is also updated to fulfilled."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")

    directive = await _make_directive(
        db_session, make_item,
        affected_item_id=door.id,
        target_source_id=schedule.id,
        property_name="finish",
        target_value="stain",
    )

    await check_directive_fulfillment(
        db_session, schedule.id, door.id, {"finish": "stain"}
    )

    snap_result = await db_session.execute(
        select(Snapshot).where(
            Snapshot.item_id == directive.id,
            Snapshot.source_id == directive.id,
        )
    )
    snap = snap_result.scalar_one()
    assert snap.properties["status"] == "fulfilled"


# ─── check_directive_fulfillment_batch ────────────────────────


@pytest.mark.asyncio
async def test_batch_fulfillment(make_item, db_session):
    """Batch fulfillment processes multiple items."""
    door1 = await make_item("door", "Door 101")
    door2 = await make_item("door", "Door 102")
    schedule = await make_item("schedule", "Schedule A")

    d1 = await _make_directive(
        db_session, make_item,
        affected_item_id=door1.id,
        target_source_id=schedule.id,
        property_name="finish",
        target_value="stain",
    )
    d2 = await _make_directive(
        db_session, make_item,
        affected_item_id=door2.id,
        target_source_id=schedule.id,
        property_name="finish",
        target_value="stain",
    )

    summary = await check_directive_fulfillment_batch(db_session, [
        (schedule.id, door1.id, {"finish": "stain"}),  # match
        (schedule.id, door2.id, {"finish": "paint"}),  # no match
    ])

    assert summary.directives_fulfilled == 1
    await db_session.refresh(d1)
    await db_session.refresh(d2)
    assert d1.properties["status"] == "fulfilled"
    assert d2.properties["status"] == "pending"
