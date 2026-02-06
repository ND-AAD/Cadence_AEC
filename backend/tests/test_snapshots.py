"""
Tests for Snapshots API — WP-5 acceptance criteria.

Key tests:
- Snapshot creation with validation
- Upsert semantics on the triple
- Context validation (must be milestone)
- Effective value uses milestone ordinal, not created_at
- Resolved view: agreed, single_source, conflicted, resolved statuses
- Effective value carry-forward from prior milestone
"""

import uuid

import pytest


# ─── Helpers ───────────────────────────────────────────────────

async def _create_item(client, item_type, identifier, properties=None):
    """Helper to create an item and return its response."""
    resp = await client.post("/api/v1/items/", json={
        "item_type": item_type,
        "identifier": identifier,
        "properties": properties or {},
    })
    assert resp.status_code == 201
    return resp.json()


async def _setup_basic_scenario(client):
    """
    Create a basic scenario: door, 2 milestones, 2 sources.
    Returns dict with all created items.
    """
    door = await _create_item(client, "door", "Door 101", {
        "mark": "D101", "width": 36, "height": 80,
    })
    dd = await _create_item(client, "milestone", "DD", {
        "name": "Design Development", "ordinal": 300,
    })
    cd = await _create_item(client, "milestone", "CD", {
        "name": "Construction Documents", "ordinal": 400,
    })
    schedule = await _create_item(client, "schedule", "Finish Schedule", {
        "name": "Finish Schedule",
    })
    spec = await _create_item(client, "specification", "Spec §08", {
        "name": "Specification Section 08",
    })
    return {
        "door": door, "dd": dd, "cd": cd,
        "schedule": schedule, "spec": spec,
    }


# ─── Snapshot Creation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_snapshot(client):
    """Can create a snapshot with the full triple."""
    s = await _setup_basic_scenario(client)

    resp = await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint", "material": "wood"},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["item_id"] == s["door"]["id"]
    assert data["context_id"] == s["dd"]["id"]
    assert data["source_id"] == s["schedule"]["id"]
    assert data["properties"]["finish"] == "paint"


@pytest.mark.asyncio
async def test_two_sources_same_item_same_context(client):
    """Can create two snapshots for the same door at DD from different sources."""
    s = await _setup_basic_scenario(client)

    # Schedule says paint
    resp1 = await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })
    assert resp1.status_code == 201

    # Spec says stain
    resp2 = await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["spec"]["id"],
        "properties": {"finish": "stain"},
    })
    assert resp2.status_code == 201

    # Both exist
    resp = await client.get(
        f"/api/v1/snapshots/?item_id={s['door']['id']}&context_id={s['dd']['id']}"
    )
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_context_must_be_milestone(client):
    """Creating snapshot with non-milestone context returns 400."""
    s = await _setup_basic_scenario(client)

    resp = await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["schedule"]["id"],  # Not a milestone!
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })
    assert resp.status_code == 400
    assert "context" in resp.json()["detail"].lower() or "milestone" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_snapshot_with_missing_item(client):
    """Snapshot referencing nonexistent item returns 404."""
    s = await _setup_basic_scenario(client)

    resp = await client.post("/api/v1/snapshots/", json={
        "item_id": str(uuid.uuid4()),
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {},
    })
    assert resp.status_code == 404


# ─── Upsert ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_same_triple(client):
    """Same triple upserts (updates properties, doesn't create duplicate)."""
    s = await _setup_basic_scenario(client)

    # First snapshot
    resp1 = await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })
    assert resp1.status_code == 201
    snap_id = resp1.json()["id"]

    # Upsert with same triple, different properties
    resp2 = await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "stain"},
    })
    assert resp2.status_code == 201
    # Same snapshot ID (upserted, not duplicated)
    assert resp2.json()["id"] == snap_id
    assert resp2.json()["properties"]["finish"] == "stain"

    # Only one snapshot exists for this triple
    resp = await client.get(
        f"/api/v1/snapshots/?item_id={s['door']['id']}"
        f"&context_id={s['dd']['id']}"
        f"&source_id={s['schedule']['id']}"
    )
    assert len(resp.json()) == 1


# ─── Effective Value ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_effective_value_basic(client):
    """Effective value returns most recent snapshot by ordinal."""
    s = await _setup_basic_scenario(client)

    # Create DD snapshot
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })

    # Create CD snapshot
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["cd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "stain"},
    })

    # Effective value should be CD (higher ordinal)
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/effective"
        f"?source={s['schedule']['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["properties"]["finish"] == "stain"
    assert data["as_of_context"]["identifier"] == "CD"


@pytest.mark.asyncio
async def test_effective_value_carry_forward(client):
    """
    Source that only submitted at DD: DD value is effective when queried at CD.

    This tests the core principle: a value is current until superseded.
    """
    s = await _setup_basic_scenario(client)

    # Only create DD snapshot — no CD submission
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })

    # Effective value should be DD (only one exists)
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/effective"
        f"?source={s['schedule']['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["properties"]["finish"] == "paint"
    assert data["as_of_context"]["identifier"] == "DD"


@pytest.mark.asyncio
async def test_effective_value_ordinal_not_created_at(client):
    """
    Effective value ordering uses milestone ordinal, not created_at.

    Test by creating DD snapshot AFTER CD snapshot — DD value should
    NOT be effective because CD has higher ordinal.
    """
    s = await _setup_basic_scenario(client)

    # Create CD snapshot FIRST (created_at is earlier)
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["cd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "stain"},
    })

    # Create DD snapshot SECOND (created_at is later, but ordinal is lower)
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })

    # Effective should be CD (ordinal 400 > 300), not DD despite DD created later
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/effective"
        f"?source={s['schedule']['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["properties"]["finish"] == "stain"
    assert data["as_of_context"]["identifier"] == "CD"


@pytest.mark.asyncio
async def test_effective_value_no_snapshots(client):
    """No snapshots from source returns 404."""
    s = await _setup_basic_scenario(client)

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/effective"
        f"?source={s['schedule']['id']}"
    )
    assert resp.status_code == 404


# ─── Resolved View ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolved_view_agreement(client):
    """Two sources agree → status='agreed'."""
    s = await _setup_basic_scenario(client)

    # Both say "paint"
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["spec"]["id"],
        "properties": {"finish": "paint"},
    })

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_count"] == 2

    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "agreed"
    assert finish["value"] == "paint"


@pytest.mark.asyncio
async def test_resolved_view_conflict(client):
    """Two sources disagree → status='conflicted'."""
    s = await _setup_basic_scenario(client)

    # Schedule says paint, spec says stain
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["spec"]["id"],
        "properties": {"finish": "stain"},
    })

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()

    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "conflicted"
    assert finish["value"] is None
    assert len(finish["sources"]) == 2


@pytest.mark.asyncio
async def test_resolved_view_single_source(client):
    """Only one source has spoken → status='single_source'."""
    s = await _setup_basic_scenario(client)

    # Only schedule speaks
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()

    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "single_source"
    assert finish["value"] == "paint"


@pytest.mark.asyncio
async def test_resolved_view_carry_forward_from_dd(client):
    """
    Schedule submitted at DD only, spec submitted at CD.
    Resolved view at CD uses schedule's DD value (carry-forward)
    compared against spec's CD value.
    """
    s = await _setup_basic_scenario(client)

    # Schedule at DD says paint
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })

    # Spec at CD says stain
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["cd"]["id"],
        "source_id": s["spec"]["id"],
        "properties": {"finish": "stain"},
    })

    # Resolved at CD: schedule's DD value vs spec's CD value
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['cd']['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_count"] == 2

    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "conflicted"
    # Both sources are represented
    assert "Finish Schedule" in finish["sources"]
    assert "Spec §08" in finish["sources"]


@pytest.mark.asyncio
async def test_resolved_view_no_snapshots(client):
    """Item with no snapshots returns empty resolved view."""
    s = await _setup_basic_scenario(client)

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_count"] == 0
    assert data["properties"] == []


@pytest.mark.asyncio
async def test_resolved_view_mixed_properties(client):
    """
    Sources address different properties:
    - 'finish' only from schedule → single_source
    - 'material' from both → agreed or conflicted
    """
    s = await _setup_basic_scenario(client)

    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint", "material": "wood"},
    })
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["spec"]["id"],
        "properties": {"material": "hollow metal"},
    })

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}"
    )
    data = resp.json()

    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    material = next(p for p in data["properties"] if p["property_name"] == "material")

    assert finish["status"] == "single_source"
    assert material["status"] == "conflicted"


@pytest.mark.asyncio
async def test_resolved_view_future_snapshots_excluded(client):
    """Resolved view at DD should NOT include CD snapshots."""
    s = await _setup_basic_scenario(client)

    # Schedule at DD says paint
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "paint"},
    })

    # Schedule at CD says stain (future relative to DD query)
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["cd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "stain"},
    })

    # Resolved at DD — should only see DD value
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}"
    )
    data = resp.json()
    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["value"] == "paint"
    assert finish["status"] == "single_source"


@pytest.mark.asyncio
async def test_resolved_view_case_insensitive_agreement(client):
    """Values that differ only in case are considered agreed."""
    s = await _setup_basic_scenario(client)

    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["schedule"]["id"],
        "properties": {"finish": "Paint"},
    })
    await client.post("/api/v1/snapshots/", json={
        "item_id": s["door"]["id"],
        "context_id": s["dd"]["id"],
        "source_id": s["spec"]["id"],
        "properties": {"finish": "PAINT"},
    })

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}"
    )
    data = resp.json()
    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "agreed"
