"""
Tests for property item navigation — WP-PROP-5.

Validates that the existing type-agnostic navigation API correctly
handles property items without code changes.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Item
from app.services.property_service import (
    ensure_property_connection,
    get_or_create_property_item,
)


@pytest_asyncio.fixture
async def nav_setup(make_item, make_connection, db_session):
    """Create navigable structure with property items."""
    project = await make_item("project", "Project Alpha")
    room = await make_item("room", "Room 203")
    door1 = await make_item("door", "Door 101")
    door2 = await make_item("door", "Door 102")

    await make_connection(project, room)
    await make_connection(room, door1)
    await make_connection(room, door2)

    # Create property items and connections
    finish_prop, _ = await get_or_create_property_item(db_session, "door", "finish")
    material_prop, _ = await get_or_create_property_item(db_session, "door", "material")
    await ensure_property_connection(db_session, finish_prop, door1)
    await ensure_property_connection(db_session, finish_prop, door2)
    await ensure_property_connection(db_session, material_prop, door1)

    await db_session.flush()

    return {
        "project": project,
        "room": room,
        "door1": door1,
        "door2": door2,
        "finish_prop": finish_prop,
        "material_prop": material_prop,
    }


@pytest.mark.asyncio
async def test_door_shows_property_items_in_connected(client: AsyncClient, nav_setup):
    """GET /api/items/:door_id/connected includes property items."""
    setup = nav_setup
    resp = await client.get(
        f"/api/v1/items/{setup['door1'].id}/connected",
        params={"direction": "both"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Connected items are grouped by type
    groups = {g["item_type"]: g for g in data["connected"]}

    # Property items should appear in the grouped response
    assert "property" in groups
    prop_ids = {p["id"] for p in groups["property"]["items"]}
    assert str(setup["finish_prop"].id) in prop_ids
    assert str(setup["material_prop"].id) in prop_ids


@pytest.mark.asyncio
async def test_property_item_shows_instances_in_connected(
    client: AsyncClient, nav_setup
):
    """GET /api/items/:property_id/connected shows door instances."""
    setup = nav_setup
    resp = await client.get(
        f"/api/v1/items/{setup['finish_prop'].id}/connected",
        params={"direction": "both"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Connected items are grouped by type
    groups = {g["item_type"]: g for g in data["connected"]}

    assert "door" in groups
    door_ids = {d["id"] for d in groups["door"]["items"]}
    assert str(setup["door1"].id) in door_ids
    assert str(setup["door2"].id) in door_ids


@pytest.mark.asyncio
async def test_bounce_back_through_property(client: AsyncClient, nav_setup):
    """Navigate Door 101 → finish property → Door 102 (bounce-back via shared property ancestor)."""
    setup = nav_setup

    # Start at project, navigate down
    breadcrumb = [str(setup["project"].id)]

    # Navigate to room
    resp = await client.post(
        "/api/v1/navigate",
        json={"breadcrumb": breadcrumb, "target": str(setup["room"].id)},
    )
    assert resp.status_code == 200
    breadcrumb = resp.json()["breadcrumb"]

    # Navigate to door1
    resp = await client.post(
        "/api/v1/navigate",
        json={"breadcrumb": breadcrumb, "target": str(setup["door1"].id)},
    )
    assert resp.status_code == 200
    breadcrumb = resp.json()["breadcrumb"]

    # Navigate to finish property
    resp = await client.post(
        "/api/v1/navigate",
        json={"breadcrumb": breadcrumb, "target": str(setup["finish_prop"].id)},
    )
    assert resp.status_code == 200
    breadcrumb = resp.json()["breadcrumb"]

    # Navigate to door2 (bounce-back: should pop to finish_prop, push door2)
    resp = await client.post(
        "/api/v1/navigate",
        json={"breadcrumb": breadcrumb, "target": str(setup["door2"].id)},
    )
    assert resp.status_code == 200
    final_breadcrumb = resp.json()["breadcrumb"]

    # Door 2 should be at the end
    assert final_breadcrumb[-1] == str(setup["door2"].id)
