"""
Tests for the Navigation API (WP-4).

Tests cover:
- Direct push: target directly connected to current item
- Sibling bounce-back: navigate to sibling connected to parent
- No path found: target unconnected to any breadcrumb ancestor
- Diamond pattern: multiple connection paths
- Target already in breadcrumb: should bounce back to it
"""

import pytest
from httpx import AsyncClient

from app.models.core import Item


@pytest.mark.asyncio
async def test_direct_push(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: breadcrumb [project, building], target=floor (floor connected to building)
    Expected: breadcrumb becomes [project, building, floor], action="push"
    """
    # Create items
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")
    floor = await make_item(item_type="floor", identifier="F1")

    # Create connections: project → building, building → floor
    await make_connection(project, building)
    await make_connection(building, floor)

    # Navigate from [project, building] to floor
    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(building.id)],
            "target": str(floor.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "push"
    assert data["bounced_from"] is None
    assert [item_id for item_id in data["breadcrumb"]] == [str(project.id), str(building.id), str(floor.id)]


@pytest.mark.asyncio
async def test_sibling_bounce_back(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: breadcrumb [project, building, floor, room, door101], target=door102
    door102 is connected to room but not to door101.
    Expected: breadcrumb becomes [project, building, floor, room, door102], action="bounce_back"
    """
    # Create items
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")
    floor = await make_item(item_type="floor", identifier="F1")
    room = await make_item(item_type="room", identifier="R1")
    door101 = await make_item(item_type="door", identifier="D101")
    door102 = await make_item(item_type="door", identifier="D102")

    # Build hierarchy
    await make_connection(project, building)
    await make_connection(building, floor)
    await make_connection(floor, room)
    await make_connection(room, door101)
    await make_connection(room, door102)

    # Navigate from breadcrumb to door102 (sibling of door101)
    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(building.id), str(floor.id), str(room.id), str(door101.id)],
            "target": str(door102.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "bounce_back"
    assert data["bounced_from"] == str(door101.id)
    assert [item_id for item_id in data["breadcrumb"]] == [
        str(project.id),
        str(building.id),
        str(floor.id),
        str(room.id),
        str(door102.id),
    ]


@pytest.mark.asyncio
async def test_no_path_found(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: breadcrumb [project], target=random_unconnected_item
    Expected: action="no_path", breadcrumb unchanged
    """
    # Create items
    project = await make_item(item_type="project", identifier="P1")
    unconnected = await make_item(item_type="building", identifier="B_unconnected")

    # No connection between them

    # Navigate from [project] to unconnected
    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id)],
            "target": str(unconnected.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "no_path"
    assert data["bounced_from"] is None
    assert data["breadcrumb"] == [str(project.id)]


@pytest.mark.asyncio
async def test_diamond_pattern(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: diamond pattern where door is connected to both schedule and spec.
    Navigate from door to schedule works.
    Expected: breadcrumb includes schedule, action="push"
    """
    # Create items: door, schedule, spec, and a connecting item
    door = await make_item(item_type="door", identifier="D1")
    schedule = await make_item(item_type="schedule", identifier="Sch1")
    spec = await make_item(item_type="specification", identifier="Spec1")
    project = await make_item(item_type="project", identifier="P1")

    # Create diamond: project → {door, schedule, spec}
    await make_connection(project, door)
    await make_connection(project, schedule)
    await make_connection(project, spec)

    # Also connect door to schedule (direct link)
    await make_connection(door, schedule)

    # Navigate from [project, door] to schedule
    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(door.id)],
            "target": str(schedule.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    # Door is directly connected to schedule, so it's a push
    assert data["action"] == "push"
    assert data["bounced_from"] is None
    assert [item_id for item_id in data["breadcrumb"]] == [str(project.id), str(door.id), str(schedule.id)]


@pytest.mark.asyncio
async def test_target_already_in_breadcrumb(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: breadcrumb [project, building, floor, room], target=building (already in breadcrumb)
    Expected: should bounce back to building, breadcrumb becomes [project, building]
    """
    # Create items
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")
    floor = await make_item(item_type="floor", identifier="F1")
    room = await make_item(item_type="room", identifier="R1")

    # Build hierarchy
    await make_connection(project, building)
    await make_connection(building, floor)
    await make_connection(floor, room)

    # Navigate to building (which is already in breadcrumb)
    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(building.id), str(floor.id), str(room.id)],
            "target": str(building.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "bounce_back"
    assert data["bounced_from"] is None
    assert [item_id for item_id in data["breadcrumb"]] == [str(project.id), str(building.id)]


@pytest.mark.asyncio
async def test_bidirectional_connection(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: connection can be traversed in both directions.
    If A → B exists, navigation should work from B to A.
    """
    # Create items
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")

    # Create connection: project → building (one direction only)
    await make_connection(project, building)

    # Navigate from [building] to project (reverse direction)
    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(building.id)],
            "target": str(project.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "push"
    assert [item_id for item_id in data["breadcrumb"]] == [str(building.id), str(project.id)]


@pytest.mark.asyncio
async def test_bounce_back_to_distant_ancestor(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: bounce back skips intermediate ancestors and finds a connected one.
    breadcrumb [project, building, floor, room], target=schedule
    schedule is connected to project (and floor), but not to room.
    Expected: bounce back to floor (or project, depending on connections)
    """
    # Create items
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")
    floor = await make_item(item_type="floor", identifier="F1")
    room = await make_item(item_type="room", identifier="R1")
    schedule = await make_item(item_type="schedule", identifier="Sch1")

    # Build hierarchy
    await make_connection(project, building)
    await make_connection(building, floor)
    await make_connection(floor, room)

    # Connect schedule to project (not to room, floor, or building)
    await make_connection(project, schedule)

    # Navigate from room to schedule
    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(building.id), str(floor.id), str(room.id)],
            "target": str(schedule.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "bounce_back"
    # Should bounce back to project (the ancestor connected to schedule)
    assert [item_id for item_id in data["breadcrumb"]] == [str(project.id), str(schedule.id)]
    assert data["bounced_from"] == str(building.id)


@pytest.mark.asyncio
async def test_missing_breadcrumb_item(
    client: AsyncClient,
    make_item,
):
    """
    Test: if a breadcrumb item doesn't exist, return 404.
    """
    import uuid

    project = await make_item(item_type="project", identifier="P1")
    fake_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(fake_id)],
            "target": str(project.id),
        },
    )

    assert response.status_code == 404
    assert "breadcrumb not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_missing_target_item(
    client: AsyncClient,
    make_item,
):
    """
    Test: if target doesn't exist, return 404.
    """
    import uuid

    project = await make_item(item_type="project", identifier="P1")
    fake_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id)],
            "target": str(fake_id),
        },
    )

    assert response.status_code == 404
    assert "target item not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_empty_breadcrumb(
    client: AsyncClient,
    make_item,
):
    """
    Test: empty breadcrumb should return 400.
    """
    project = await make_item(item_type="project", identifier="P1")

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [],
            "target": str(project.id),
        },
    )

    assert response.status_code == 400
    assert "breadcrumb cannot be empty" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_complex_navigation_sequence(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: complex navigation sequence with multiple push and bounce-back operations.
    """
    # Create a more complex hierarchy
    project = await make_item(item_type="project", identifier="P1")
    building1 = await make_item(item_type="building", identifier="B1")
    building2 = await make_item(item_type="building", identifier="B2")
    floor1 = await make_item(item_type="floor", identifier="F1")
    floor2 = await make_item(item_type="floor", identifier="F2")

    # Connections
    await make_connection(project, building1)
    await make_connection(project, building2)
    await make_connection(building1, floor1)
    await make_connection(building2, floor2)

    # Step 1: Push from project to building1
    response1 = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id)],
            "target": str(building1.id),
        },
    )
    assert response1.json()["action"] == "push"

    # Step 2: Push from building1 to floor1
    response2 = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(building1.id)],
            "target": str(floor1.id),
        },
    )
    assert response2.json()["action"] == "push"

    # Step 3: Bounce back to building2 (connected to project)
    response3 = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(building1.id), str(floor1.id)],
            "target": str(building2.id),
        },
    )
    assert response3.json()["action"] == "bounce_back"
    assert response3.json()["breadcrumb"] == [str(project.id), str(building2.id)]
