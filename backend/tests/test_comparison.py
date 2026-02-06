"""
Tests for temporal comparison API — WP-8.

Tests the POST /api/v1/compare endpoint with various scenarios:
- Added/removed/modified/unchanged items
- Source filtering
- Effective value merging
- Carry-forward semantics
- Pagination
- Error cases
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Snapshot


@pytest.mark.asyncio
async def test_compare_simple_modified_items(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
    make_connection,
):
    """
    Test comparing 50 doors between DD and CD where 10 have changed finish.
    Verifies 10 modified, 40 unchanged.
    """
    # Create milestones with ordinals
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    # Create a source (e.g., spec)
    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    # Create 50 doors
    doors = []
    for i in range(50):
        door = await make_item(
            item_type="door",
            identifier=f"Door-{i:03d}",
        )
        doors.append(door)

    # Create snapshots at DD for all doors
    for i, door in enumerate(doors):
        finish = "wood" if i < 40 else "glass"
        snapshot = Snapshot(
            item_id=door.id,
            context_id=dd.id,
            source_id=spec.id,
            properties={"finish": finish, "width": "36\""},
        )
        db_session.add(snapshot)

    # Create snapshots at CD for all doors
    for i, door in enumerate(doors):
        # Last 10 (indices 40-49) have changed finish to metal
        if i >= 40:
            finish = "metal"
        else:
            finish = "wood"
        snapshot = Snapshot(
            item_id=door.id,
            context_id=cd.id,
            source_id=spec.id,
            properties={"finish": finish, "width": "36\""},
        )
        db_session.add(snapshot)

    await db_session.commit()

    # Perform comparison
    response = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(d.id) for d in doors],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
        },
    )

    assert response.status_code == 200
    result = response.json()

    # Check summary
    assert result["summary"]["modified"] == 10
    assert result["summary"]["unchanged"] == 40
    assert result["summary"]["added"] == 0
    assert result["summary"]["removed"] == 0
    assert result["summary"]["total"] == 50

    # Verify the 10 modified items are the last ones
    modified_items = [item for item in result["items"] if item["category"] == "modified"]
    assert len(modified_items) == 10

    for item in modified_items:
        assert len(item["changes"]) == 1
        change = item["changes"][0]
        assert change["property_name"] == "finish"
        assert change["old_value"] == "glass"
        assert change["new_value"] == "metal"


@pytest.mark.asyncio
async def test_compare_added_items(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test detecting items that exist at CD but not DD (added).
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    # Create two doors
    door1 = await make_item(item_type="door", identifier="Door-001")
    door2 = await make_item(item_type="door", identifier="Door-002")

    # Only add snapshot for door1 at DD
    snapshot_dd = Snapshot(
        item_id=door1.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    db_session.add(snapshot_dd)

    # Add snapshots for both at CD
    snapshot_cd_1 = Snapshot(
        item_id=door1.id,
        context_id=cd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    snapshot_cd_2 = Snapshot(
        item_id=door2.id,
        context_id=cd.id,
        source_id=spec.id,
        properties={"finish": "glass"},
    )
    db_session.add(snapshot_cd_1)
    db_session.add(snapshot_cd_2)

    await db_session.commit()

    response = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(door1.id), str(door2.id)],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
        },
    )

    assert response.status_code == 200
    result = response.json()

    assert result["summary"]["added"] == 1
    assert result["summary"]["unchanged"] == 1
    assert result["summary"]["modified"] == 0
    assert result["summary"]["removed"] == 0

    added_item = [item for item in result["items"] if item["category"] == "added"][0]
    assert added_item["item_id"] == str(door2.id)


@pytest.mark.asyncio
async def test_compare_removed_items(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test detecting items that exist at DD but not CD (removed).
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    door1 = await make_item(item_type="door", identifier="Door-001")
    door2 = await make_item(item_type="door", identifier="Door-002")

    # Add snapshots for both at DD
    snapshot_dd_1 = Snapshot(
        item_id=door1.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    snapshot_dd_2 = Snapshot(
        item_id=door2.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={"finish": "glass"},
    )
    db_session.add(snapshot_dd_1)
    db_session.add(snapshot_dd_2)

    # Only add snapshot for door1 at CD
    snapshot_cd = Snapshot(
        item_id=door1.id,
        context_id=cd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    db_session.add(snapshot_cd)

    await db_session.commit()

    response = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(door1.id), str(door2.id)],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
        },
    )

    assert response.status_code == 200
    result = response.json()

    # With carry-forward semantics, door2's DD snapshot is still effective
    # at CD (a value is current until superseded). So door2 is unchanged.
    assert result["summary"]["removed"] == 0
    assert result["summary"]["unchanged"] == 2
    assert result["summary"]["modified"] == 0
    assert result["summary"]["added"] == 0


@pytest.mark.asyncio
async def test_compare_source_filter_works(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test that source_filter correctly ignores other sources.

    Create a door with snapshots from both schedule and spec,
    but only schedule makes a change. Verify that with spec filter,
    it shows unchanged, and with schedule filter, it shows modified.
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    schedule = await make_item(
        item_type="schedule",
        identifier="Schedule",
    )
    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    door = await make_item(item_type="door", identifier="Door-001")

    # Schedule: door changes finish from wood to metal
    schedule_dd = Snapshot(
        item_id=door.id,
        context_id=dd.id,
        source_id=schedule.id,
        properties={"finish": "wood"},
    )
    schedule_cd = Snapshot(
        item_id=door.id,
        context_id=cd.id,
        source_id=schedule.id,
        properties={"finish": "metal"},
    )
    db_session.add(schedule_dd)
    db_session.add(schedule_cd)

    # Spec: door stays wood in both
    spec_dd = Snapshot(
        item_id=door.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    spec_cd = Snapshot(
        item_id=door.id,
        context_id=cd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    db_session.add(spec_dd)
    db_session.add(spec_cd)

    await db_session.commit()

    # Compare with spec filter: should be unchanged
    response_spec = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(door.id)],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
        },
    )

    assert response_spec.status_code == 200
    result_spec = response_spec.json()
    assert result_spec["summary"]["unchanged"] == 1
    assert result_spec["summary"]["modified"] == 0

    # Compare with schedule filter: should be modified
    response_schedule = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(door.id)],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(schedule.id),
        },
    )

    assert response_schedule.status_code == 200
    result_schedule = response_schedule.json()
    assert result_schedule["summary"]["modified"] == 1
    assert result_schedule["summary"]["unchanged"] == 0


@pytest.mark.asyncio
async def test_compare_property_changes_show_values(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test that property-level changes show old and new values correctly.
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    door = await make_item(item_type="door", identifier="Door-001")

    snapshot_dd = Snapshot(
        item_id=door.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={
            "finish": "wood",
            "width": "36\"",
            "height": "84\"",
        },
    )
    snapshot_cd = Snapshot(
        item_id=door.id,
        context_id=cd.id,
        source_id=spec.id,
        properties={
            "finish": "glass",
            "width": "36\"",
            "height": "84\"",
            "hardware": "chrome",
        },
    )
    db_session.add(snapshot_dd)
    db_session.add(snapshot_cd)

    await db_session.commit()

    response = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(door.id)],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
        },
    )

    assert response.status_code == 200
    result = response.json()

    item = result["items"][0]
    assert item["category"] == "modified"
    assert len(item["changes"]) == 2  # finish changed, hardware added

    changes_by_name = {c["property_name"]: c for c in item["changes"]}

    # Check finish change
    assert changes_by_name["finish"]["old_value"] == "wood"
    assert changes_by_name["finish"]["new_value"] == "glass"

    # Check hardware addition
    assert changes_by_name["hardware"]["old_value"] is None
    assert changes_by_name["hardware"]["new_value"] == "chrome"


@pytest.mark.asyncio
async def test_compare_no_items_returns_empty(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test that comparing with no items returns empty result.
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    response = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
        },
    )

    assert response.status_code == 200
    result = response.json()

    assert result["summary"]["total"] == 0
    assert result["items"] == []


@pytest.mark.asyncio
async def test_compare_invalid_context_non_milestone(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test that comparing with a non-milestone context returns 400.
    """
    door = await make_item(
        item_type="door",
        identifier="Door-001",
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    response = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(door.id)],
            "from_context_id": str(door.id),  # Invalid: not a milestone
            "to_context_id": str(cd.id),
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_compare_pagination_works(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test that pagination with limit/offset works correctly.
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    # Create 25 doors
    doors = []
    for i in range(25):
        door = await make_item(
            item_type="door",
            identifier=f"Door-{i:03d}",
        )
        doors.append(door)
        snapshot = Snapshot(
            item_id=door.id,
            context_id=dd.id,
            source_id=spec.id,
            properties={"finish": "wood"},
        )
        db_session.add(snapshot)
        snapshot = Snapshot(
            item_id=door.id,
            context_id=cd.id,
            source_id=spec.id,
            properties={"finish": "wood"},
        )
        db_session.add(snapshot)

    await db_session.commit()

    # Request first 10
    response1 = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(d.id) for d in doors],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
            "limit": 10,
            "offset": 0,
        },
    )

    assert response1.status_code == 200
    result1 = response1.json()
    assert len(result1["items"]) == 10
    assert result1["limit"] == 10
    assert result1["offset"] == 0
    assert result1["summary"]["total"] == 25  # Total is still 25

    # Request next 10
    response2 = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(d.id) for d in doors],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
            "limit": 10,
            "offset": 10,
        },
    )

    assert response2.status_code == 200
    result2 = response2.json()
    assert len(result2["items"]) == 10
    assert result2["offset"] == 10

    # Request last 5
    response3 = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(d.id) for d in doors],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
            "limit": 10,
            "offset": 20,
        },
    )

    assert response3.status_code == 200
    result3 = response3.json()
    assert len(result3["items"]) == 5


@pytest.mark.asyncio
async def test_compare_parent_item_children(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
    make_connection,
):
    """
    Test comparing all children of a parent item.
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    # Create a parent (building) and children (rooms)
    building = await make_item(
        item_type="building",
        identifier="Main Building",
    )

    rooms = []
    for i in range(5):
        room = await make_item(
            item_type="room",
            identifier=f"Room-{i:03d}",
        )
        rooms.append(room)

        # Connect building → room
        await make_connection(building, room)

        # Create snapshots
        snapshot_dd = Snapshot(
            item_id=room.id,
            context_id=dd.id,
            source_id=spec.id,
            properties={"count": i},
        )
        snapshot_cd = Snapshot(
            item_id=room.id,
            context_id=cd.id,
            source_id=spec.id,
            properties={"count": i + 1} if i < 2 else {"count": i},
        )
        db_session.add(snapshot_dd)
        db_session.add(snapshot_cd)

    await db_session.commit()

    # Compare using parent_item_id
    response = await client.post(
        "/api/v1/compare",
        json={
            "parent_item_id": str(building.id),
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
        },
    )

    assert response.status_code == 200
    result = response.json()

    # Should have 2 modified (first two rooms) and 3 unchanged
    assert result["summary"]["modified"] == 2
    assert result["summary"]["unchanged"] == 3
    assert result["summary"]["total"] == 5


@pytest.mark.asyncio
async def test_compare_carry_forward_logic(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test carry-forward: item has DD snapshot but not CD → uses DD values (unchanged, not removed).

    This tests the effective value logic: if an item has a snapshot at DD
    and no snapshot at CD, the DD value carries forward and the item should
    be categorized as 'unchanged', not 'removed'.
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    door = await make_item(item_type="door", identifier="Door-001")

    # Create snapshot only at DD
    snapshot_dd = Snapshot(
        item_id=door.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    db_session.add(snapshot_dd)

    await db_session.commit()

    # Compare without source filter (using effective values)
    # Door should carry forward from DD to CD, so it's unchanged, not removed
    response = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(door.id)],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            # No source_filter: uses effective values from all sources
        },
    )

    assert response.status_code == 200
    result = response.json()

    assert result["summary"]["unchanged"] == 1
    assert result["summary"]["removed"] == 0


@pytest.mark.asyncio
async def test_compare_multiple_sources_effective_values(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test multiple sources: use effective values from all sources when no filter.

    Create a door with snapshots from two sources at DD and CD.
    When comparing without source_filter, properties from both sources
    should be merged and compared.
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    schedule = await make_item(
        item_type="schedule",
        identifier="Schedule",
    )
    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    door = await make_item(item_type="door", identifier="Door-001")

    # Schedule provides finish
    schedule_dd = Snapshot(
        item_id=door.id,
        context_id=dd.id,
        source_id=schedule.id,
        properties={"finish": "wood"},
    )
    schedule_cd = Snapshot(
        item_id=door.id,
        context_id=cd.id,
        source_id=schedule.id,
        properties={"finish": "wood"},  # No change
    )
    db_session.add(schedule_dd)
    db_session.add(schedule_cd)

    # Spec provides width and changes hardware
    spec_dd = Snapshot(
        item_id=door.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={"width": "36\"", "hardware": "wood"},
    )
    spec_cd = Snapshot(
        item_id=door.id,
        context_id=cd.id,
        source_id=spec.id,
        properties={"width": "36\"", "hardware": "chrome"},  # Hardware changed
    )
    db_session.add(spec_dd)
    db_session.add(spec_cd)

    await db_session.commit()

    # Compare without source_filter: merge from both sources
    response = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [str(door.id)],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            # No source_filter
        },
    )

    assert response.status_code == 200
    result = response.json()

    # Door should be modified because hardware changed
    assert result["summary"]["modified"] == 1
    assert result["summary"]["unchanged"] == 0

    item = result["items"][0]
    assert item["category"] == "modified"

    # Should have one change: hardware
    assert len(item["changes"]) == 1
    change = item["changes"][0]
    assert change["property_name"] == "hardware"
    assert change["old_value"] == "wood"
    assert change["new_value"] == "chrome"


@pytest.mark.asyncio
async def test_compare_summary_counts_correct(
    client: AsyncClient,
    db_session: AsyncSession,
    make_item,
):
    """
    Test that summary counts are correct across all categories.
    """
    dd = await make_item(
        item_type="milestone",
        identifier="DD",
        properties={"ordinal": 100},
    )
    cd = await make_item(
        item_type="milestone",
        identifier="CD",
        properties={"ordinal": 200},
    )

    spec = await make_item(
        item_type="specification",
        identifier="Spec",
    )

    # Create different categories
    door_added = await make_item(item_type="door", identifier="Door-Added")
    door_removed = await make_item(item_type="door", identifier="Door-Removed")
    door_modified = await make_item(item_type="door", identifier="Door-Modified")
    door_unchanged = await make_item(item_type="door", identifier="Door-Unchanged")

    # Added: exists at CD but not DD
    snapshot_added_cd = Snapshot(
        item_id=door_added.id,
        context_id=cd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    db_session.add(snapshot_added_cd)

    # Removed: exists at DD but not CD
    snapshot_removed_dd = Snapshot(
        item_id=door_removed.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    db_session.add(snapshot_removed_dd)

    # Modified: exists at both but values differ
    snapshot_modified_dd = Snapshot(
        item_id=door_modified.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    snapshot_modified_cd = Snapshot(
        item_id=door_modified.id,
        context_id=cd.id,
        source_id=spec.id,
        properties={"finish": "glass"},
    )
    db_session.add(snapshot_modified_dd)
    db_session.add(snapshot_modified_cd)

    # Unchanged: exists at both and values match
    snapshot_unchanged_dd = Snapshot(
        item_id=door_unchanged.id,
        context_id=dd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    snapshot_unchanged_cd = Snapshot(
        item_id=door_unchanged.id,
        context_id=cd.id,
        source_id=spec.id,
        properties={"finish": "wood"},
    )
    db_session.add(snapshot_unchanged_dd)
    db_session.add(snapshot_unchanged_cd)

    await db_session.commit()

    response = await client.post(
        "/api/v1/compare",
        json={
            "item_ids": [
                str(door_added.id),
                str(door_removed.id),
                str(door_modified.id),
                str(door_unchanged.id),
            ],
            "from_context_id": str(dd.id),
            "to_context_id": str(cd.id),
            "source_filter": str(spec.id),
        },
    )

    assert response.status_code == 200
    result = response.json()

    assert result["summary"]["added"] == 1
    # With carry-forward, DD-only item is unchanged at CD (value current until superseded)
    assert result["summary"]["removed"] == 0
    assert result["summary"]["modified"] == 1
    assert result["summary"]["unchanged"] == 2  # includes carry-forward item
    assert result["summary"]["total"] == 4
