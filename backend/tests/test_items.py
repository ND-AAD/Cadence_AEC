"""Tests for Items API — WP-2 acceptance criteria."""

import uuid

import pytest
import pytest_asyncio


# ─── Create ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_item(client):
    """Can create items of any configured type."""
    response = await client.post("/api/v1/items/", json={
        "item_type": "door",
        "identifier": "Door 101",
        "properties": {"width": 36, "height": 80},
    })
    assert response.status_code == 201
    data = response.json()
    assert data["item_type"] == "door"
    assert data["identifier"] == "Door 101"
    assert data["properties"]["width"] == 36


@pytest.mark.asyncio
async def test_create_item_unknown_type(client):
    """Unknown item type returns 400."""
    response = await client.post("/api/v1/items/", json={
        "item_type": "unicorn",
        "identifier": "test",
    })
    assert response.status_code == 400
    assert "Unknown item type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_various_types(client):
    """Can create items of every category."""
    types = ["project", "building", "floor", "room", "door",
             "schedule", "specification", "milestone", "phase",
             "change", "conflict", "decision", "note"]
    for item_type in types:
        response = await client.post("/api/v1/items/", json={
            "item_type": item_type,
            "identifier": f"test-{item_type}",
        })
        assert response.status_code == 201, f"Failed for type: {item_type}"


# ─── Read ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_item(client):
    """Get single item by ID."""
    create = await client.post("/api/v1/items/", json={
        "item_type": "room",
        "identifier": "Room 203",
    })
    item_id = create.json()["id"]

    response = await client.get(f"/api/v1/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["identifier"] == "Room 203"


@pytest.mark.asyncio
async def test_get_item_not_found(client):
    """Missing item returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/items/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_items_with_type_filter(client):
    """List with type filter returns only matching items."""
    await client.post("/api/v1/items/", json={"item_type": "door", "identifier": "D1"})
    await client.post("/api/v1/items/", json={"item_type": "room", "identifier": "R1"})
    await client.post("/api/v1/items/", json={"item_type": "door", "identifier": "D2"})

    response = await client.get("/api/v1/items/?item_type=door")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(i["item_type"] == "door" for i in data["items"])


@pytest.mark.asyncio
async def test_list_items_pagination(client):
    """Pagination returns correct slices and total."""
    for i in range(5):
        await client.post("/api/v1/items/", json={
            "item_type": "door",
            "identifier": f"D{i}",
        })

    response = await client.get("/api/v1/items/?limit=2&offset=0")
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2

    response = await client.get("/api/v1/items/?limit=2&offset=4")
    data = response.json()
    assert len(data["items"]) == 1


# ─── Update ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_properties_merge(client):
    """Properties merge correctly — existing keys preserved."""
    create = await client.post("/api/v1/items/", json={
        "item_type": "door",
        "identifier": "D101",
        "properties": {"width": 36, "height": 80, "finish": "paint"},
    })
    item_id = create.json()["id"]

    # Update only 'finish' — width and height should survive
    response = await client.patch(f"/api/v1/items/{item_id}", json={
        "properties": {"finish": "stain"},
    })
    assert response.status_code == 200
    props = response.json()["properties"]
    assert props["finish"] == "stain"
    assert props["width"] == 36
    assert props["height"] == 80


@pytest.mark.asyncio
async def test_update_identifier(client):
    """Can update just the identifier."""
    create = await client.post("/api/v1/items/", json={
        "item_type": "door",
        "identifier": "D101",
    })
    item_id = create.json()["id"]

    response = await client.patch(f"/api/v1/items/{item_id}", json={
        "identifier": "DR-101",
    })
    assert response.json()["identifier"] == "DR-101"


# ─── Types Endpoint ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_types(client):
    """Types endpoint returns all registered types with config."""
    response = await client.get("/api/v1/items/types")
    assert response.status_code == 200
    data = response.json()
    assert "door" in data
    assert "milestone" in data
    assert data["door"]["category"] == "spatial"
    assert data["milestone"]["is_context_type"] is True
    assert data["schedule"]["is_source_type"] is True


# ─── Connected Items ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_connected_items_grouped_by_type(client):
    """Connected items are returned grouped by item_type."""
    # Create a room with doors and a schedule
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "Room 203",
    })).json()
    door1 = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()
    door2 = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D102",
    })).json()
    schedule = (await client.post("/api/v1/items/", json={
        "item_type": "schedule", "identifier": "Finish Schedule",
    })).json()

    # Room → Door connections
    await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"], "target_item_id": door1["id"],
    })
    await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"], "target_item_id": door2["id"],
    })
    # Schedule → Door connection (incoming to room's door)
    await client.post("/api/v1/connections/", json={
        "source_item_id": schedule["id"], "target_item_id": room["id"],
    })

    # Get connected items for room
    response = await client.get(f"/api/v1/items/{room['id']}/connected")
    assert response.status_code == 200
    data = response.json()

    assert data["item"]["identifier"] == "Room 203"
    type_names = [g["item_type"] for g in data["connected"]]
    assert "door" in type_names
    assert "schedule" in type_names

    door_group = next(g for g in data["connected"] if g["item_type"] == "door")
    assert door_group["count"] == 2


@pytest.mark.asyncio
async def test_connected_items_excludes_breadcrumb(client):
    """Exclude parameter filters out breadcrumb ancestors."""
    project = (await client.post("/api/v1/items/", json={
        "item_type": "project", "identifier": "Alpha",
    })).json()
    building = (await client.post("/api/v1/items/", json={
        "item_type": "building", "identifier": "Building A",
    })).json()
    floor = (await client.post("/api/v1/items/", json={
        "item_type": "floor", "identifier": "Floor 1",
    })).json()

    await client.post("/api/v1/connections/", json={
        "source_item_id": project["id"], "target_item_id": building["id"],
    })
    await client.post("/api/v1/connections/", json={
        "source_item_id": building["id"], "target_item_id": floor["id"],
    })

    # From floor, without exclusion — building appears
    response = await client.get(f"/api/v1/items/{floor['id']}/connected")
    data = response.json()
    all_ids = [item["id"] for g in data["connected"] for item in g["items"]]
    assert building["id"] in all_ids

    # From floor, with building excluded (it's in breadcrumb)
    response = await client.get(
        f"/api/v1/items/{floor['id']}/connected?exclude={building['id']}"
    )
    data = response.json()
    all_ids = [item["id"] for g in data["connected"] for item in g["items"]]
    assert building["id"] not in all_ids


@pytest.mark.asyncio
async def test_connected_items_both_directions(client):
    """Direction=both returns items from outgoing AND incoming connections."""
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "Room 203",
    })).json()
    floor = (await client.post("/api/v1/items/", json={
        "item_type": "floor", "identifier": "Floor 1",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()

    # floor → room (room is target)
    await client.post("/api/v1/connections/", json={
        "source_item_id": floor["id"], "target_item_id": room["id"],
    })
    # room → door (room is source)
    await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"], "target_item_id": door["id"],
    })

    # From room with direction=both, should see both floor and door
    response = await client.get(f"/api/v1/items/{room['id']}/connected?direction=both")
    data = response.json()
    all_ids = [item["id"] for g in data["connected"] for item in g["items"]]
    assert floor["id"] in all_ids
    assert door["id"] in all_ids


@pytest.mark.asyncio
async def test_connected_items_action_counts(client):
    """Connected items should include action_counts with changes and conflicts counts."""
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()
    change1 = (await client.post("/api/v1/items/", json={
        "item_type": "change", "identifier": "CH1",
    })).json()
    change2 = (await client.post("/api/v1/items/", json={
        "item_type": "change", "identifier": "CH2",
    })).json()
    conflict1 = (await client.post("/api/v1/items/", json={
        "item_type": "conflict", "identifier": "CF1",
    })).json()
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "R101",
    })).json()

    # Create connections: room → door, change1 → door, change2 → door, conflict1 → door
    await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"], "target_item_id": door["id"],
    })
    await client.post("/api/v1/connections/", json={
        "source_item_id": change1["id"], "target_item_id": door["id"],
    })
    await client.post("/api/v1/connections/", json={
        "source_item_id": change2["id"], "target_item_id": door["id"],
    })
    await client.post("/api/v1/connections/", json={
        "source_item_id": conflict1["id"], "target_item_id": door["id"],
    })

    # Get connected items from room
    response = await client.get(f"/api/v1/items/{room['id']}/connected")
    data = response.json()

    # Find door in the connected items
    door_item = None
    for group in data["connected"]:
        for item in group["items"]:
            if item["id"] == door["id"]:
                door_item = item
                break

    assert door_item is not None, "Door should be connected to room"
    assert "action_counts" in door_item, "action_counts should be present"
    assert door_item["action_counts"]["changes"] == 2, f"Expected 2 changes, got {door_item['action_counts']['changes']}"
    assert door_item["action_counts"]["conflicts"] == 1, f"Expected 1 conflict, got {door_item['action_counts']['conflicts']}"


# ─── Milestone Navigation (Snapshot-aware) ───────────────────

@pytest.mark.asyncio
async def test_milestone_connected_shows_snapshot_items(client):
    """Navigating into a milestone shows items that have snapshots at that context.

    This is the core test: 'dive into 50% CD and see what was submitted.'
    Doors with snapshots at CD appear; doors without snapshots at CD do not.
    """
    # Create milestone, source, and doors
    milestone = (await client.post("/api/v1/items/", json={
        "item_type": "milestone", "identifier": "CD",
        "properties": {"name": "Construction Documents", "ordinal": 400},
    })).json()
    schedule = (await client.post("/api/v1/items/", json={
        "item_type": "schedule", "identifier": "Door Schedule",
        "properties": {"name": "Door Schedule"},
    })).json()
    door1 = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "Door 101",
    })).json()
    door2 = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "Door 103",
    })).json()
    door_not_submitted = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "Door 102",
    })).json()

    # Create snapshots at CD for door1 and door2 (but NOT door_not_submitted)
    await client.post("/api/v1/snapshots/", json={
        "item_id": door1["id"], "context_id": milestone["id"],
        "source_id": schedule["id"], "properties": {"finish": "paint"},
    })
    await client.post("/api/v1/snapshots/", json={
        "item_id": door2["id"], "context_id": milestone["id"],
        "source_id": schedule["id"], "properties": {"finish": "stain"},
    })

    # Navigate into the milestone
    response = await client.get(f"/api/v1/items/{milestone['id']}/connected")
    assert response.status_code == 200
    data = response.json()

    # Should see the doors that were submitted
    type_names = [g["item_type"] for g in data["connected"]]
    assert "door" in type_names

    door_group = next(g for g in data["connected"] if g["item_type"] == "door")
    door_ids = {d["id"] for d in door_group["items"]}
    assert door1["id"] in door_ids, "Door 101 was submitted at CD"
    assert door2["id"] in door_ids, "Door 103 was submitted at CD"
    assert door_not_submitted["id"] not in door_ids, "Door 102 was NOT submitted"
    assert door_group["count"] == 2


@pytest.mark.asyncio
async def test_milestone_connected_shows_sources(client):
    """Navigating into a milestone shows the sources that submitted at that context."""
    milestone = (await client.post("/api/v1/items/", json={
        "item_type": "milestone", "identifier": "DD",
        "properties": {"name": "Design Development", "ordinal": 300},
    })).json()
    schedule = (await client.post("/api/v1/items/", json={
        "item_type": "schedule", "identifier": "Door Schedule",
        "properties": {"name": "Door Schedule"},
    })).json()
    spec = (await client.post("/api/v1/items/", json={
        "item_type": "specification", "identifier": "Div 08",
        "properties": {"name": "Div 08 - Openings"},
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "Door 201",
    })).json()

    # Both sources submit snapshots at DD
    await client.post("/api/v1/snapshots/", json={
        "item_id": door["id"], "context_id": milestone["id"],
        "source_id": schedule["id"], "properties": {"finish": "paint"},
    })
    await client.post("/api/v1/snapshots/", json={
        "item_id": door["id"], "context_id": milestone["id"],
        "source_id": spec["id"], "properties": {"finish": "paint"},
    })

    # Navigate into milestone
    response = await client.get(f"/api/v1/items/{milestone['id']}/connected")
    data = response.json()

    type_names = [g["item_type"] for g in data["connected"]]
    assert "schedule" in type_names, "Schedule submitted at DD"
    assert "specification" in type_names, "Spec submitted at DD"


@pytest.mark.asyncio
async def test_milestone_connected_deduplicates(client):
    """Items reachable via both Connection and Snapshot appear only once."""
    milestone = (await client.post("/api/v1/items/", json={
        "item_type": "milestone", "identifier": "CD",
        "properties": {"name": "CD", "ordinal": 400},
    })).json()
    schedule = (await client.post("/api/v1/items/", json={
        "item_type": "schedule", "identifier": "Schedule A",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "Door 301",
    })).json()

    # Create an explicit Connection: milestone → door
    await client.post("/api/v1/connections/", json={
        "source_item_id": milestone["id"], "target_item_id": door["id"],
    })

    # Also create a Snapshot: (door, CD, schedule)
    await client.post("/api/v1/snapshots/", json={
        "item_id": door["id"], "context_id": milestone["id"],
        "source_id": schedule["id"], "properties": {"finish": "paint"},
    })

    # Navigate into milestone — door should appear exactly once
    response = await client.get(f"/api/v1/items/{milestone['id']}/connected")
    data = response.json()

    door_group = next(
        (g for g in data["connected"] if g["item_type"] == "door"), None
    )
    assert door_group is not None
    assert door_group["count"] == 1, "Door should appear exactly once despite dual reachability"


@pytest.mark.asyncio
async def test_milestone_connected_respects_type_filter(client):
    """Type filter works with snapshot-derived items."""
    milestone = (await client.post("/api/v1/items/", json={
        "item_type": "milestone", "identifier": "SD",
        "properties": {"name": "SD", "ordinal": 200},
    })).json()
    schedule = (await client.post("/api/v1/items/", json={
        "item_type": "schedule", "identifier": "Sched",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D-401",
    })).json()
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "Room 100",
    })).json()

    # Snapshots at SD for both door and room
    await client.post("/api/v1/snapshots/", json={
        "item_id": door["id"], "context_id": milestone["id"],
        "source_id": schedule["id"], "properties": {"finish": "paint"},
    })
    await client.post("/api/v1/snapshots/", json={
        "item_id": room["id"], "context_id": milestone["id"],
        "source_id": schedule["id"], "properties": {"finish_floor": "tile"},
    })

    # Filter to only doors
    response = await client.get(
        f"/api/v1/items/{milestone['id']}/connected?types=door"
    )
    data = response.json()

    type_names = [g["item_type"] for g in data["connected"]]
    assert "door" in type_names
    assert "room" not in type_names, "Room should be filtered out"


@pytest.mark.asyncio
async def test_milestone_connected_respects_exclude(client):
    """Exclude parameter works with snapshot-derived items."""
    project = (await client.post("/api/v1/items/", json={
        "item_type": "project", "identifier": "Test Project",
    })).json()
    milestone = (await client.post("/api/v1/items/", json={
        "item_type": "milestone", "identifier": "CD",
        "properties": {"name": "CD", "ordinal": 400},
    })).json()
    schedule = (await client.post("/api/v1/items/", json={
        "item_type": "schedule", "identifier": "Sched",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D-501",
    })).json()

    # Project → milestone connection (structural)
    await client.post("/api/v1/connections/", json={
        "source_item_id": project["id"], "target_item_id": milestone["id"],
    })

    # Snapshot at CD
    await client.post("/api/v1/snapshots/", json={
        "item_id": door["id"], "context_id": milestone["id"],
        "source_id": schedule["id"], "properties": {"finish": "paint"},
    })

    # Navigate into milestone, excluding project from breadcrumb
    response = await client.get(
        f"/api/v1/items/{milestone['id']}/connected?exclude={project['id']}"
    )
    data = response.json()

    # Project should be excluded, door and schedule should remain
    all_ids = set()
    for group in data["connected"]:
        for item in group["items"]:
            all_ids.add(item["id"])

    assert project["id"] not in all_ids, "Project excluded by breadcrumb"
    assert door["id"] in all_ids, "Door visible via snapshot"


@pytest.mark.asyncio
async def test_non_context_type_ignores_snapshot_query(client):
    """Regular spatial items don't trigger the snapshot-aware query."""
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "Room 600",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D-601",
    })).json()
    milestone = (await client.post("/api/v1/items/", json={
        "item_type": "milestone", "identifier": "DD",
        "properties": {"ordinal": 300},
    })).json()
    schedule = (await client.post("/api/v1/items/", json={
        "item_type": "schedule", "identifier": "Sched",
    })).json()

    # Connection: room → door
    await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"], "target_item_id": door["id"],
    })

    # Snapshot at DD for the room itself (room is the item, not a context)
    await client.post("/api/v1/snapshots/", json={
        "item_id": room["id"], "context_id": milestone["id"],
        "source_id": schedule["id"], "properties": {"finish_floor": "tile"},
    })

    # Navigate into room — should only see connection-based items
    response = await client.get(f"/api/v1/items/{room['id']}/connected")
    data = response.json()

    type_names = [g["item_type"] for g in data["connected"]]
    assert "door" in type_names
    # Should NOT see milestone or schedule just because room has a snapshot
    # (room is spatial, not a context type)
    assert "milestone" not in type_names
    assert "schedule" not in type_names
