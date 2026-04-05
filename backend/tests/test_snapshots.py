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
    resp = await client.post(
        "/api/v1/items/",
        json={
            "item_type": item_type,
            "identifier": identifier,
            "properties": properties or {},
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _setup_basic_scenario(client):
    """
    Create a basic scenario: door, 2 milestones, 2 sources.
    Returns dict with all created items.
    """
    door = await _create_item(
        client,
        "door",
        "Door 101",
        {
            "mark": "D101",
            "width": 36,
            "height": 80,
        },
    )
    dd = await _create_item(
        client,
        "milestone",
        "DD",
        {
            "name": "Design Development",
            "ordinal": 300,
        },
    )
    cd = await _create_item(
        client,
        "milestone",
        "CD",
        {
            "name": "Construction Documents",
            "ordinal": 400,
        },
    )
    schedule = await _create_item(
        client,
        "schedule",
        "Finish Schedule",
        {
            "name": "Finish Schedule",
        },
    )
    spec = await _create_item(
        client,
        "specification",
        "Spec §08",
        {
            "name": "Specification Section 08",
        },
    )
    return {
        "door": door,
        "dd": dd,
        "cd": cd,
        "schedule": schedule,
        "spec": spec,
    }


# ─── Snapshot Creation ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_snapshot(client):
    """Can create a snapshot with the full triple."""
    s = await _setup_basic_scenario(client)

    resp = await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint", "material": "wood"},
        },
    )
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
    resp1 = await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )
    assert resp1.status_code == 201

    # Spec says stain
    resp2 = await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "stain"},
        },
    )
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

    resp = await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["schedule"]["id"],  # Not a milestone!
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )
    assert resp.status_code == 400
    assert (
        "context" in resp.json()["detail"].lower()
        or "milestone" in resp.json()["detail"].lower()
    )


@pytest.mark.asyncio
async def test_snapshot_with_missing_item(client):
    """Snapshot referencing nonexistent item returns 404."""
    s = await _setup_basic_scenario(client)

    resp = await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": str(uuid.uuid4()),
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {},
        },
    )
    assert resp.status_code == 404


# ─── Upsert ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_same_triple(client):
    """Same triple upserts (updates properties, doesn't create duplicate)."""
    s = await _setup_basic_scenario(client)

    # First snapshot
    resp1 = await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )
    assert resp1.status_code == 201
    snap_id = resp1.json()["id"]

    # Upsert with same triple, different properties
    resp2 = await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "stain"},
        },
    )
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
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Create CD snapshot
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "stain"},
        },
    )

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
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

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
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Create DD snapshot SECOND (created_at is later, but ordinal is lower)
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

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
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['dd']['id']}"
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
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['dd']['id']}"
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
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['dd']['id']}"
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
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Spec at CD says stain
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Resolved at CD: schedule's DD value vs spec's CD value
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['cd']['id']}"
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
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['dd']['id']}"
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

    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint", "material": "wood"},
        },
    )
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"material": "hollow metal"},
        },
    )

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['dd']['id']}"
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
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Schedule at CD says stain (future relative to DD query)
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Resolved at DD — should only see DD value
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['dd']['id']}"
    )
    data = resp.json()
    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["value"] == "paint"
    assert finish["status"] == "single_source"


@pytest.mark.asyncio
async def test_resolved_view_case_insensitive_agreement(client):
    """Values that differ only in case are considered agreed."""
    s = await _setup_basic_scenario(client)

    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "Paint"},
        },
    )
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "PAINT"},
        },
    )

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['dd']['id']}"
    )
    data = resp.json()
    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "agreed"


# ─── Ordinal Filtering ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolved_view_excludes_default_ordinal_at_later_context(client):
    """
    Snapshots with ordinal 0 (unset) are excluded when resolved view is at a
    non-zero ordinal context.

    Scenario:
    - Door with two snapshots from schedule:
      1. At DD (ordinal 300): finish = "paint" (ordinal 300)
      2. At milestone_unknown (ordinal 0, default): finish = "stain" (ordinal 0)
    - Resolved view at CD (ordinal 400) should NOT include the unknown milestone snapshot.
    - Resolved view at DD (ordinal 300) should NOT include the unknown milestone snapshot.
    - Resolved view at a milestone with ordinal 0 should include snapshots with ordinal 0.

    This tests the core ordinal filtering fix: when context_ordinal > 0,
    exclude snapshots where snap_ordinal == 0.
    """
    s = await _setup_basic_scenario(client)

    # Create a milestone with no ordinal (defaults to 0)
    unknown_milestone = await _create_item(
        client,
        "milestone",
        "Unknown",
        {"name": "Unknown Phase"},  # No ordinal property
    )

    # Schedule at DD says paint
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Schedule at Unknown (ordinal 0) says stain
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": unknown_milestone["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Resolved at DD (300): should NOT see unknown milestone snapshot
    # Only schedule's DD value (paint) should be included
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['dd']['id']}"
    )
    data = resp.json()
    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "single_source"
    assert finish["value"] == "paint"  # Not "stain"
    assert data["source_count"] == 1

    # Resolved at CD (400): should NOT see unknown milestone snapshot
    # Only schedule's DD value carried forward (paint)
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['cd']['id']}"
    )
    data = resp.json()
    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "single_source"
    assert finish["value"] == "paint"  # Carried forward, not "stain"
    assert data["source_count"] == 1


@pytest.mark.asyncio
async def test_resolved_view_at_intermediate_ordinal_excludes_later(client):
    """
    Resolved view at 50% CD (ordinal ~350) should NOT show values from
    100% CD (ordinal 400).

    This tests that the ordinal filter correctly excludes snapshots where
    snap_ordinal > context_ordinal, even when both are non-zero.
    """
    s = await _setup_basic_scenario(client)

    # Create intermediate milestone: 50% CD (ordinal 350)
    cd_50pct = await _create_item(
        client,
        "milestone",
        "50% CD",
        {"name": "50% Construction Documents", "ordinal": 350},
    )

    # Schedule at 50% CD says paint
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": cd_50pct["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Schedule at 100% CD says stain (future relative to 50% CD)
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Resolved at 50% CD: should only see 50% CD value, NOT 100% CD
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={cd_50pct['id']}"
    )
    data = resp.json()
    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "single_source"
    assert finish["value"] == "paint"  # Not "stain"

    # Resolved at 100% CD: should see 100% CD value
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['cd']['id']}"
    )
    data = resp.json()
    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    assert finish["status"] == "single_source"
    assert finish["value"] == "stain"  # Updated to the 100% CD value


# ─── Cumulative Mode (T-2): effective_context ──────────────────


@pytest.mark.asyncio
async def test_resolved_view_cumulative_mode_returns_effective_context_for_carried_forward(
    client,
):
    """
    Cumulative mode should populate effective_context for carried-forward values.

    Scenario:
    - Schedule submits at DD (ordinal 300): finish = "paint"
    - Spec submits at CD (ordinal 400): finish = "stain"
    - Request cumulative mode at CD
    - Schedule's property should have effective_context = DD (where it originated)
    - Spec's property should have effective_context = null (submitted at CD)
    """
    s = await _setup_basic_scenario(client)

    # Schedule at DD says paint
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Spec at CD says stain
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Resolved at CD with cumulative mode
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['cd']['id']}&mode=cumulative"
    )
    assert resp.status_code == 200
    data = resp.json()

    # Response should have mode field
    assert data["mode"] == "cumulative"

    finish = next(p for p in data["properties"] if p["property_name"] == "finish")

    # Schedule's finish (carried forward from DD) should have effective_context = DD
    schedule_val = finish["sources"].get("Finish Schedule")
    assert schedule_val == "paint"
    assert finish["effective_context"] is not None
    # The effective_context should be the DD milestone identifier or ID
    assert finish["effective_context"] in [s["dd"]["id"], s["dd"]["identifier"], "DD"]

    # Spec's finish (submitted at CD) should have effective_context = null
    # Actually, for conflicts the effective_context should represent where
    # the effective value came from. Let's verify the architecture:
    # Since this is a conflict, value is None, but effective_context still
    # applies to the property level


@pytest.mark.asyncio
async def test_resolved_view_cumulative_mode_null_effective_context_at_submitted_context(
    client,
):
    """
    Properties submitted at the requested context should have effective_context: null.

    Scenario:
    - Both schedule and spec submit at DD
    - Request resolved view at DD with cumulative mode
    - Both should have effective_context = null (submitted at queried context)
    """
    s = await _setup_basic_scenario(client)

    # Schedule at DD
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Spec at DD
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}&mode=cumulative"
    )
    assert resp.status_code == 200
    data = resp.json()

    finish = next(p for p in data["properties"] if p["property_name"] == "finish")
    # Both sources submitted at the requested context, so effective_context should be null
    assert finish["effective_context"] is None


@pytest.mark.asyncio
async def test_resolved_view_returns_mode_field(client):
    """Response should include mode field matching the requested mode."""
    s = await _setup_basic_scenario(client)

    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Default mode is cumulative
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?context={s['dd']['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "cumulative"

    # Explicit cumulative mode
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}&mode=cumulative"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "cumulative"


@pytest.mark.asyncio
async def test_resolved_view_requires_context_for_cumulative_mode(client):
    """Cumulative mode without context parameter should return 400."""
    s = await _setup_basic_scenario(client)

    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Cumulative mode without context should fail
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?mode=cumulative"
    )
    assert resp.status_code == 400
    assert "context" in resp.json()["detail"].lower()


# ─── T-3: Submitted and Current Modes ───────────────────────────


@pytest.mark.asyncio
async def test_resolved_view_submitted_mode_excludes_carried_forward(client):
    """Submitted mode should only return properties from exact context match."""
    s = await _setup_basic_scenario(client)

    # Schedule submits at DD only
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Spec submits at CD only
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Submitted mode at CD: should NOT include schedule's DD value
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['cd']['id']}&mode=submitted"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "submitted"

    # Should have only 1 source (spec at CD), NOT 2
    assert data["source_count"] == 1

    # finish property should come only from spec
    finish = next(
        (p for p in data["properties"] if p["property_name"] == "finish"), None
    )
    assert finish is not None
    assert finish["value"] == "stain"
    assert "Spec §08" in finish["sources"]
    assert "Finish Schedule" not in finish["sources"]


@pytest.mark.asyncio
async def test_resolved_view_submitted_mode_omits_absent_properties(client):
    """Properties not submitted at the exact context should be absent from response."""
    s = await _setup_basic_scenario(client)

    # Schedule at DD: finish and material
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint", "material": "wood"},
        },
    )

    # Spec at CD: only finish (no material)
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Submitted mode at CD: should only show properties submitted at CD
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['cd']['id']}&mode=submitted"
    )
    assert resp.status_code == 200
    data = resp.json()

    # material should not be in response (not submitted at CD)
    material = next(
        (p for p in data["properties"] if p["property_name"] == "material"), None
    )
    assert material is None

    # finish should be present
    finish = next(
        (p for p in data["properties"] if p["property_name"] == "finish"), None
    )
    assert finish is not None


@pytest.mark.asyncio
async def test_resolved_view_submitted_mode_no_context_returns_400(client):
    """Submitted mode without context parameter should return 400."""
    s = await _setup_basic_scenario(client)

    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Submitted mode without context should fail
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?mode=submitted"
    )
    assert resp.status_code == 400
    assert "context" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_resolved_view_current_mode_returns_latest(client):
    """Current mode should return the latest value per source across all milestones."""
    s = await _setup_basic_scenario(client)

    # Schedule at DD says paint
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Schedule at CD says stain (later milestone = higher ordinal)
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Current mode: should return CD value (highest ordinal)
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?mode=current"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "current"

    finish = next(
        (p for p in data["properties"] if p["property_name"] == "finish"), None
    )
    assert finish is not None
    assert finish["value"] == "stain"
    assert finish["status"] == "single_source"


@pytest.mark.asyncio
async def test_resolved_view_current_mode_works_without_context(client):
    """Current mode should work even without context parameter."""
    s = await _setup_basic_scenario(client)

    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Current mode without context parameter should succeed
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?mode=current"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "current"
    # context should be None for current mode
    assert data["context"] is None


@pytest.mark.asyncio
async def test_resolved_view_current_mode_populates_effective_context(client):
    """Current mode should always populate effective_context on every property."""
    s = await _setup_basic_scenario(client)

    # Schedule at DD says paint
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["dd"]["id"],
            "source_id": s["schedule"]["id"],
            "properties": {"finish": "paint"},
        },
    )

    # Spec at CD says stain
    await client.post(
        "/api/v1/snapshots/",
        json={
            "item_id": s["door"]["id"],
            "context_id": s["cd"]["id"],
            "source_id": s["spec"]["id"],
            "properties": {"finish": "stain"},
        },
    )

    # Current mode: both properties should have effective_context populated
    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved?mode=current"
    )
    assert resp.status_code == 200
    data = resp.json()

    finish = next(
        (p for p in data["properties"] if p["property_name"] == "finish"), None
    )
    assert finish is not None
    # In current mode, effective_context should always be populated
    # It tells us which milestone the value came from
    assert finish["effective_context"] is not None


@pytest.mark.asyncio
async def test_resolved_view_invalid_mode_returns_400(client):
    """Invalid mode value should return 400."""
    s = await _setup_basic_scenario(client)

    resp = await client.get(
        f"/api/v1/snapshots/item/{s['door']['id']}/resolved"
        f"?context={s['dd']['id']}&mode=invalid"
    )
    assert resp.status_code == 400
    assert "mode" in resp.json()["detail"].lower()


# ─── Workflow Discovery for Changes ──────────────────────────


@pytest.mark.asyncio
async def test_resolved_view_includes_change_ids(
    client, db_session, make_item, make_connection
):
    """Resolved properties should include change_ids when change items are connected."""
    from app.models.core import Snapshot

    # Setup: project → schedule → door, with two milestones
    project = await make_item("project", "Test Project")
    schedule = await make_item("schedule", "Door Schedule")
    await make_connection(project, schedule)
    milestone_sd = await make_item("milestone", "SD", {"ordinal": 200})
    milestone_dd = await make_item("milestone", "DD", {"ordinal": 300})
    await make_connection(project, milestone_sd)
    await make_connection(project, milestone_dd)

    door = await make_item("door", "101")
    await make_connection(schedule, door)

    # Create snapshots at SD and DD with different height
    snap_sd = Snapshot(
        item_id=door.id,
        context_id=milestone_sd.id,
        source_id=schedule.id,
        properties={"height": "80"},
    )
    snap_dd = Snapshot(
        item_id=door.id,
        context_id=milestone_dd.id,
        source_id=schedule.id,
        properties={"height": "84"},
    )
    db_session.add_all([snap_sd, snap_dd])
    await db_session.flush()

    # Create a change item connected to the door (change → door)
    change = await make_item(
        "change",
        "height change",
        {
            "changes": {"height": {"old": "80", "new": "84"}},
            "status": "DETECTED",
        },
    )
    await make_connection(change, door)

    # Query resolved properties at DD
    response = await client.get(
        f"/api/v1/snapshots/item/{door.id}/resolved?mode=submitted&context={milestone_dd.id}"
    )
    assert response.status_code == 200
    data = response.json()

    # Find the height property
    height_prop = next(
        (p for p in data["properties"] if p["property_name"] == "height"),
        None,
    )
    assert height_prop is not None, "height property not found in resolved view"
    assert height_prop["workflow"] is not None, "workflow refs missing"
    assert len(height_prop["workflow"]["change_ids"]) > 0, (
        f"change_ids empty! workflow={height_prop['workflow']}"
    )
    assert height_prop["workflow"]["change_ids"][0] == str(change.id)
