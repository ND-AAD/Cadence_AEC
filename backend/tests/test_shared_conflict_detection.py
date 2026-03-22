"""
Tests for shared conflict_detection module — WP-18.0.

Covers:
  - get_or_create_conflict: idempotent creation, source pair canonicalization
  - get_effective_snapshots: correct filtering by source, ordinal, excluded types
  - detect_conflicts_for_item: disagreement → conflict, agreement → auto-resolve
  - detect_conflicts_batch: batch processing over multiple items
"""

import uuid

import pytest

from app.models.core import Snapshot
from app.services.conflict_detection import (
    get_or_create_conflict,
    get_effective_snapshots,
    detect_conflicts_for_item,
    detect_conflicts_batch,
)


# ─── get_or_create_conflict ────────────────────────────────────


@pytest.mark.asyncio
async def test_create_conflict_new(make_item, db_session):
    """First call creates a new conflict item."""
    door = await make_item("door", "Door 101")
    source_a = uuid.uuid4()
    source_b = uuid.uuid4()

    conflict, is_new = await get_or_create_conflict(
        db_session, door, "finish", source_a, source_b
    )

    assert is_new is True
    assert conflict.item_type == "conflict"
    assert conflict.identifier.startswith("Door 101 / finish / ")
    assert conflict.properties["property_name"] == "finish"
    assert conflict.properties["status"] == "detected"


@pytest.mark.asyncio
async def test_create_conflict_idempotent(make_item, db_session):
    """Second call returns same conflict, is_new=False."""
    door = await make_item("door", "Door 101")
    source_a = uuid.uuid4()
    source_b = uuid.uuid4()

    conflict1, is_new1 = await get_or_create_conflict(
        db_session, door, "finish", source_a, source_b
    )
    conflict2, is_new2 = await get_or_create_conflict(
        db_session, door, "finish", source_a, source_b
    )

    assert is_new1 is True
    assert is_new2 is False
    assert conflict1.id == conflict2.id


@pytest.mark.asyncio
async def test_source_pair_canonicalization(make_item, db_session):
    """Swapping source_a and source_b gives same conflict."""
    door = await make_item("door", "Door 101")
    source_a = uuid.uuid4()
    source_b = uuid.uuid4()

    conflict1, _ = await get_or_create_conflict(
        db_session, door, "finish", source_a, source_b
    )
    conflict2, is_new = await get_or_create_conflict(
        db_session, door, "finish", source_b, source_a
    )

    assert is_new is False
    assert conflict1.id == conflict2.id


@pytest.mark.asyncio
async def test_different_properties_different_conflicts(make_item, db_session):
    """Different property names produce distinct conflicts."""
    door = await make_item("door", "Door 101")
    source_a = uuid.uuid4()
    source_b = uuid.uuid4()

    c1, _ = await get_or_create_conflict(db_session, door, "finish", source_a, source_b)
    c2, is_new = await get_or_create_conflict(
        db_session, door, "material", source_a, source_b
    )

    assert is_new is True
    assert c1.id != c2.id


@pytest.mark.asyncio
async def test_different_source_pairs_different_conflicts(make_item, db_session):
    """Different source pairs produce distinct conflicts (Decision 9)."""
    door = await make_item("door", "Door 101")
    sa, sb, sc = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    c1, _ = await get_or_create_conflict(db_session, door, "finish", sa, sb)
    c2, is_new = await get_or_create_conflict(db_session, door, "finish", sa, sc)

    assert is_new is True
    assert c1.id != c2.id


# ─── get_effective_snapshots ─────────────────────────────────


@pytest.mark.asyncio
async def test_effective_snapshots_excludes_current_source(make_item, db_session):
    """Current source's snapshots are excluded."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")
    milestone = await make_item("milestone", "DD", {"ordinal": 100})

    db_session.add(
        Snapshot(
            item_id=door.id,
            context_id=milestone.id,
            source_id=schedule.id,
            properties={"finish": "paint"},
        )
    )
    await db_session.flush()

    # Asking for other sources from schedule's perspective → empty
    result = await get_effective_snapshots(db_session, door.id, schedule.id, 100)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_effective_snapshots_returns_other_sources(make_item, db_session):
    """Other source's snapshots are returned."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")
    spec = await make_item("specification", "Spec B")
    milestone = await make_item("milestone", "DD", {"ordinal": 100})

    db_session.add(
        Snapshot(
            item_id=door.id,
            context_id=milestone.id,
            source_id=schedule.id,
            properties={"finish": "paint"},
        )
    )
    await db_session.flush()

    # From spec's perspective, schedule is another source
    result = await get_effective_snapshots(db_session, door.id, spec.id, 100)
    assert schedule.id in result
    assert result[schedule.id].properties["finish"] == "paint"


@pytest.mark.asyncio
async def test_effective_snapshots_respects_ordinal(make_item, db_session):
    """Only snapshots at or before context ordinal are effective."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")
    spec = await make_item("specification", "Spec B")
    dd = await make_item("milestone", "DD", {"ordinal": 100})
    cd = await make_item("milestone", "CD", {"ordinal": 200})

    # Schedule has snapshot at DD and CD
    db_session.add(
        Snapshot(
            item_id=door.id,
            context_id=dd.id,
            source_id=schedule.id,
            properties={"finish": "paint"},
        )
    )
    db_session.add(
        Snapshot(
            item_id=door.id,
            context_id=cd.id,
            source_id=schedule.id,
            properties={"finish": "stain"},
        )
    )
    await db_session.flush()

    # At DD ordinal, only DD snapshot is effective
    result = await get_effective_snapshots(db_session, door.id, spec.id, 100)
    assert result[schedule.id].properties["finish"] == "paint"

    # At CD ordinal, CD snapshot is effective (most recent)
    result2 = await get_effective_snapshots(db_session, door.id, spec.id, 200)
    assert result2[schedule.id].properties["finish"] == "stain"


# ─── detect_conflicts_for_item ───────────────────────────────


@pytest.mark.asyncio
async def test_detect_conflict_on_disagreement(make_item, db_session):
    """Disagreement creates a conflict."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")
    spec = await make_item("specification", "Spec B")
    milestone = await make_item("milestone", "DD", {"ordinal": 100})

    # Schedule says finish=paint
    db_session.add(
        Snapshot(
            item_id=door.id,
            context_id=milestone.id,
            source_id=schedule.id,
            properties={"finish": "paint"},
        )
    )
    await db_session.flush()

    # Spec says finish=stain → conflict
    conflicts, resolutions = await detect_conflicts_for_item(
        db_session, door, spec.id, milestone, {"finish": "stain"}
    )

    assert len(conflicts) == 1
    assert conflicts[0].is_new is True
    assert conflicts[0].property_name == "finish"
    assert len(resolutions) == 0


@pytest.mark.asyncio
async def test_no_conflict_on_agreement(make_item, db_session):
    """Agreement produces no conflicts."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")
    spec = await make_item("specification", "Spec B")
    milestone = await make_item("milestone", "DD", {"ordinal": 100})

    db_session.add(
        Snapshot(
            item_id=door.id,
            context_id=milestone.id,
            source_id=schedule.id,
            properties={"finish": "paint"},
        )
    )
    await db_session.flush()

    conflicts, resolutions = await detect_conflicts_for_item(
        db_session, door, spec.id, milestone, {"finish": "paint"}
    )

    assert len(conflicts) == 0
    assert len(resolutions) == 0


@pytest.mark.asyncio
async def test_auto_resolution_on_agreement(make_item, db_session):
    """Agreement auto-resolves a prior conflict."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")
    spec = await make_item("specification", "Spec B")
    dd = await make_item("milestone", "DD", {"ordinal": 100})
    cd = await make_item("milestone", "CD", {"ordinal": 200})

    # Schedule says paint at DD
    db_session.add(
        Snapshot(
            item_id=door.id,
            context_id=dd.id,
            source_id=schedule.id,
            properties={"finish": "paint"},
        )
    )
    await db_session.flush()

    # Spec says stain at DD → conflict
    conflicts, _ = await detect_conflicts_for_item(
        db_session, door, spec.id, dd, {"finish": "stain"}
    )
    assert len(conflicts) == 1

    # Now schedule agrees at CD (changed to stain)
    db_session.add(
        Snapshot(
            item_id=door.id,
            context_id=cd.id,
            source_id=schedule.id,
            properties={"finish": "stain"},
        )
    )
    await db_session.flush()

    # Spec still says stain at CD → auto-resolve
    _, resolutions = await detect_conflicts_for_item(
        db_session, door, spec.id, cd, {"finish": "stain"}
    )
    assert len(resolutions) == 1

    # Verify conflict status updated
    conflict_item = conflicts[0].conflict_item
    await db_session.refresh(conflict_item)
    assert conflict_item.properties["status"] == "resolved_by_agreement"


@pytest.mark.asyncio
async def test_no_conflict_when_other_source_lacks_property(make_item, db_session):
    """If other source doesn't have the property, no conflict."""
    door = await make_item("door", "Door 101")
    schedule = await make_item("schedule", "Schedule A")
    spec = await make_item("specification", "Spec B")
    milestone = await make_item("milestone", "DD", {"ordinal": 100})

    # Schedule only has 'finish', not 'fire_rating'
    db_session.add(
        Snapshot(
            item_id=door.id,
            context_id=milestone.id,
            source_id=schedule.id,
            properties={"finish": "paint"},
        )
    )
    await db_session.flush()

    # Spec asserts fire_rating (schedule has no fire_rating) → no conflict
    conflicts, _ = await detect_conflicts_for_item(
        db_session, door, spec.id, milestone, {"fire_rating": "90 min"}
    )
    assert len(conflicts) == 0


# ─── detect_conflicts_batch ──────────────────────────────────


@pytest.mark.asyncio
async def test_batch_detection(make_item, db_session):
    """Batch detection processes multiple items."""
    door1 = await make_item("door", "Door 101")
    door2 = await make_item("door", "Door 102")
    schedule = await make_item("schedule", "Schedule A")
    spec = await make_item("specification", "Spec B")
    milestone = await make_item("milestone", "DD", {"ordinal": 100})

    # Schedule: both doors finish=paint
    for door in [door1, door2]:
        db_session.add(
            Snapshot(
                item_id=door.id,
                context_id=milestone.id,
                source_id=schedule.id,
                properties={"finish": "paint"},
            )
        )
    await db_session.flush()

    # Spec: door1 finish=stain (conflict), door2 finish=paint (agree)
    items_with_snaps = [
        (door1, spec.id, milestone, {"finish": "stain"}),
        (door2, spec.id, milestone, {"finish": "paint"}),
    ]
    summary = await detect_conflicts_batch(db_session, items_with_snaps)

    assert summary.new_conflicts == 1
    assert summary.resolved_conflicts == 0
    assert len(summary.conflicts) == 1
    assert summary.conflicts[0].affected_item_id == door1.id
