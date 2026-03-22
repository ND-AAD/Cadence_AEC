"""
Tests for Decision 13: Status Transition Endpoints.

Covers:
  - POST /items/{id}/start-review (detected → in_review)
  - POST /items/{id}/hold (any active → hold, stores pre_hold_status)
  - POST /items/{id}/resume-review (hold → restored pre-hold status)
  - Invalid transitions (wrong status, wrong item type)
  - Snapshot consistency (self-sourced snapshot updated alongside item)
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Item, Snapshot


# ─── Fixtures ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def detected_conflict(db_session: AsyncSession, make_item):
    """A conflict item in 'detected' status with a self-sourced snapshot."""
    conflict = await make_item(
        "conflict",
        "Door 101 / finish / abc+def",
        {"status": "detected", "property_name": "finish"},
    )
    # Self-sourced snapshot (standard pattern for workflow items)
    snap = Snapshot(
        item_id=conflict.id,
        context_id=conflict.id,  # Using self as context for simplicity
        source_id=conflict.id,
        properties={"status": "detected", "property_name": "finish"},
    )
    db_session.add(snap)
    await db_session.flush()
    return conflict


@pytest_asyncio.fixture
async def detected_change(db_session: AsyncSession, make_item):
    """A change item in 'detected' status with a self-sourced snapshot."""
    change = await make_item(
        "change",
        "Door 101 / finish / DD→CD",
        {"status": "detected", "property_name": "finish"},
    )
    snap = Snapshot(
        item_id=change.id,
        context_id=change.id,
        source_id=change.id,
        properties={"status": "detected", "property_name": "finish"},
    )
    db_session.add(snap)
    await db_session.flush()
    return change


@pytest_asyncio.fixture
async def pending_directive(db_session: AsyncSession, make_item):
    """A directive item in 'pending' status with a self-sourced snapshot."""
    directive = await make_item(
        "directive",
        "Directive: Door 101 / finish → Spec",
        {"status": "pending", "property_name": "finish"},
    )
    snap = Snapshot(
        item_id=directive.id,
        context_id=directive.id,
        source_id=directive.id,
        properties={"status": "pending", "property_name": "finish"},
    )
    db_session.add(snap)
    await db_session.flush()
    return directive


# ─── Helper ──────────────────────────────────────────────────


async def get_self_snapshot(
    db_session: AsyncSession, item_id: uuid.UUID
) -> Snapshot | None:
    """Load the self-sourced snapshot for a workflow item."""
    result = await db_session.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == item_id,
                Snapshot.source_id == item_id,
            )
        )
    )
    return result.scalar_one_or_none()


# ─── Start Review ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_review_conflict(client, detected_conflict, db_session):
    """Start review transitions conflict from detected → in_review."""
    resp = await client.post(f"/api/v1/items/{detected_conflict.id}/start-review")
    assert resp.status_code == 200

    data = resp.json()
    assert data["item_id"] == str(detected_conflict.id)
    assert data["item_type"] == "conflict"
    assert data["previous_status"] == "detected"
    assert data["new_status"] == "in_review"

    # Verify item properties updated
    await db_session.refresh(detected_conflict)
    assert detected_conflict.properties["status"] == "in_review"

    # Verify self-sourced snapshot updated
    snap = await get_self_snapshot(db_session, detected_conflict.id)
    assert snap is not None
    assert snap.properties["status"] == "in_review"


@pytest.mark.asyncio
async def test_start_review_change(client, detected_change, db_session):
    """Start review works on change items too."""
    resp = await client.post(f"/api/v1/items/{detected_change.id}/start-review")
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "in_review"


@pytest.mark.asyncio
async def test_start_review_invalid_status(client, detected_conflict, db_session):
    """Cannot start review on an item already in_review."""
    # First transition to in_review
    await client.post(f"/api/v1/items/{detected_conflict.id}/start-review")

    # Second attempt should fail
    resp = await client.post(f"/api/v1/items/{detected_conflict.id}/start-review")
    assert resp.status_code == 400
    assert "Cannot start review" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_start_review_nonworkflow_item(client, make_item):
    """Cannot start review on a non-workflow item (e.g., door)."""
    door = await make_item("door", "Door 101")
    resp = await client.post(f"/api/v1/items/{door.id}/start-review")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_review_not_found(client):
    """404 for nonexistent item."""
    fake_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/items/{fake_id}/start-review")
    assert resp.status_code == 404


# ─── Hold ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hold_from_detected(client, detected_conflict, db_session):
    """Hold from detected stores pre_hold_status."""
    resp = await client.post(f"/api/v1/items/{detected_conflict.id}/hold")
    assert resp.status_code == 200

    data = resp.json()
    assert data["previous_status"] == "detected"
    assert data["new_status"] == "hold"

    await db_session.refresh(detected_conflict)
    assert detected_conflict.properties["status"] == "hold"
    assert detected_conflict.properties["pre_hold_status"] == "detected"


@pytest.mark.asyncio
async def test_hold_from_in_review(client, detected_conflict, db_session):
    """Hold from in_review stores 'in_review' as pre_hold_status."""
    # First transition to in_review
    await client.post(f"/api/v1/items/{detected_conflict.id}/start-review")

    # Then hold
    resp = await client.post(f"/api/v1/items/{detected_conflict.id}/hold")
    assert resp.status_code == 200
    assert resp.json()["previous_status"] == "in_review"

    await db_session.refresh(detected_conflict)
    assert detected_conflict.properties["pre_hold_status"] == "in_review"


@pytest.mark.asyncio
async def test_hold_directive_from_pending(client, pending_directive, db_session):
    """Hold works on directives from pending status."""
    resp = await client.post(f"/api/v1/items/{pending_directive.id}/hold")
    assert resp.status_code == 200
    assert resp.json()["previous_status"] == "pending"

    await db_session.refresh(pending_directive)
    assert pending_directive.properties["status"] == "hold"
    assert pending_directive.properties["pre_hold_status"] == "pending"


@pytest.mark.asyncio
async def test_hold_already_held(client, detected_conflict):
    """Cannot hold an item already on hold."""
    await client.post(f"/api/v1/items/{detected_conflict.id}/hold")
    resp = await client.post(f"/api/v1/items/{detected_conflict.id}/hold")
    assert resp.status_code == 400
    assert "Cannot hold" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_hold_snapshot_updated(client, detected_conflict, db_session):
    """Self-sourced snapshot reflects hold status."""
    await client.post(f"/api/v1/items/{detected_conflict.id}/hold")

    snap = await get_self_snapshot(db_session, detected_conflict.id)
    assert snap is not None
    assert snap.properties["status"] == "hold"


# ─── Resume Review ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resume_restores_detected(client, detected_conflict, db_session):
    """Resume from hold restores 'detected' pre-hold status."""
    await client.post(f"/api/v1/items/{detected_conflict.id}/hold")
    resp = await client.post(f"/api/v1/items/{detected_conflict.id}/resume-review")
    assert resp.status_code == 200

    data = resp.json()
    assert data["previous_status"] == "hold"
    assert data["new_status"] == "detected"

    await db_session.refresh(detected_conflict)
    assert detected_conflict.properties["status"] == "detected"
    assert "pre_hold_status" not in detected_conflict.properties


@pytest.mark.asyncio
async def test_resume_restores_in_review(client, detected_conflict, db_session):
    """Resume from hold restores 'in_review' when that was the pre-hold state."""
    # detected → in_review → hold → resume → in_review
    await client.post(f"/api/v1/items/{detected_conflict.id}/start-review")
    await client.post(f"/api/v1/items/{detected_conflict.id}/hold")
    resp = await client.post(f"/api/v1/items/{detected_conflict.id}/resume-review")

    assert resp.status_code == 200
    assert resp.json()["new_status"] == "in_review"

    await db_session.refresh(detected_conflict)
    assert detected_conflict.properties["status"] == "in_review"


@pytest.mark.asyncio
async def test_resume_not_on_hold(client, detected_conflict):
    """Cannot resume an item that isn't on hold."""
    resp = await client.post(f"/api/v1/items/{detected_conflict.id}/resume-review")
    assert resp.status_code == 400
    assert "Cannot resume review" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_resume_snapshot_updated(client, detected_conflict, db_session):
    """Self-sourced snapshot reflects restored status after resume."""
    await client.post(f"/api/v1/items/{detected_conflict.id}/hold")
    await client.post(f"/api/v1/items/{detected_conflict.id}/resume-review")

    snap = await get_self_snapshot(db_session, detected_conflict.id)
    assert snap is not None
    assert snap.properties["status"] == "detected"


# ─── Full Lifecycle ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_lifecycle(client, detected_conflict, db_session):
    """
    Full lifecycle: detected → in_review → hold → resume (in_review) → hold → resume
    Verifies the cycle works correctly through multiple transitions.
    """
    item_id = detected_conflict.id

    # detected → in_review
    resp = await client.post(f"/api/v1/items/{item_id}/start-review")
    assert resp.status_code == 200

    # in_review → hold
    resp = await client.post(f"/api/v1/items/{item_id}/hold")
    assert resp.status_code == 200

    # hold → in_review (resume)
    resp = await client.post(f"/api/v1/items/{item_id}/resume-review")
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "in_review"

    # in_review → hold (second hold)
    resp = await client.post(f"/api/v1/items/{item_id}/hold")
    assert resp.status_code == 200

    # hold → in_review (second resume)
    resp = await client.post(f"/api/v1/items/{item_id}/resume-review")
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "in_review"

    # Final state check
    await db_session.refresh(detected_conflict)
    assert detected_conflict.properties["status"] == "in_review"
    assert "pre_hold_status" not in detected_conflict.properties
