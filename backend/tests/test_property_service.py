"""
Tests for property_service.py — WP-PROP-1.

Covers:
  - get_or_create_property_item: creation, idempotency, registered vs unregistered
  - ensure_property_connection: creation, idempotency
  - get_property_items_for_type: filtering by parent type
  - seed_property_items_from_config: bulk creation from type config
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Connection, Item
from app.services.property_service import (
    ensure_property_connection,
    get_or_create_property_item,
    get_property_items_for_type,
    seed_property_items_from_config,
)


@pytest.mark.asyncio
async def test_create_registered_property(db_session: AsyncSession):
    """Property item created with metadata from PropertyDef."""
    prop, is_new = await get_or_create_property_item(db_session, "door", "fire_rating")
    assert is_new is True
    assert prop.identifier == "door/fire_rating"
    assert prop.item_type == "property"
    assert prop.properties["property_name"] == "fire_rating"
    assert prop.properties["parent_type"] == "door"
    assert prop.properties["label"] == "Fire Rating"
    assert prop.properties["data_type"] == "string"


@pytest.mark.asyncio
async def test_create_unregistered_property(db_session: AsyncSession):
    """Unregistered property gets fallback metadata."""
    prop, is_new = await get_or_create_property_item(
        db_session, "door", "acoustic_rating"
    )
    assert is_new is True
    assert prop.identifier == "door/acoustic_rating"
    assert prop.properties["label"] == "Acoustic Rating"
    assert prop.properties["data_type"] == "string"


@pytest.mark.asyncio
async def test_idempotent_creation(db_session: AsyncSession):
    """Second call returns same item, is_new=False."""
    prop1, new1 = await get_or_create_property_item(db_session, "door", "finish")
    prop2, new2 = await get_or_create_property_item(db_session, "door", "finish")
    assert new1 is True
    assert new2 is False
    assert prop1.id == prop2.id


@pytest.mark.asyncio
async def test_type_scoping(db_session: AsyncSession):
    """door/finish and room/finish are different items."""
    door_prop, _ = await get_or_create_property_item(db_session, "door", "finish")
    room_prop, _ = await get_or_create_property_item(db_session, "room", "finish")
    assert door_prop.id != room_prop.id
    assert door_prop.identifier == "door/finish"
    assert room_prop.identifier == "room/finish"


@pytest.mark.asyncio
async def test_ensure_property_connection(db_session: AsyncSession, make_item):
    """Connection created property → instance."""
    prop, _ = await get_or_create_property_item(db_session, "door", "finish")
    door = await make_item("door", "Door 101")

    created = await ensure_property_connection(db_session, prop, door)
    assert created is True

    # Idempotent
    created2 = await ensure_property_connection(db_session, prop, door)
    assert created2 is False

    # Verify connection direction
    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == prop.id,
            Connection.target_item_id == door.id,
        )
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_get_property_items_for_type(db_session: AsyncSession):
    """Returns only properties for the requested parent type."""
    await get_or_create_property_item(db_session, "door", "finish")
    await get_or_create_property_item(db_session, "door", "material")
    await get_or_create_property_item(db_session, "room", "finish")

    door_props = await get_property_items_for_type(db_session, "door")
    assert len(door_props) == 2

    room_props = await get_property_items_for_type(db_session, "room")
    assert len(room_props) == 1


@pytest.mark.asyncio
async def test_seed_from_config(db_session: AsyncSession):
    """Seed creates items for all PropertyDefs on the type."""
    items = await seed_property_items_from_config(db_session, "door")
    # door type has 22 PropertyDefs in type_config.py
    assert len(items) >= 10  # at least the core ones; exact count depends on config

    # Idempotent
    items2 = await seed_property_items_from_config(db_session, "door")
    assert len(items2) == len(items)
    assert {i.id for i in items} == {i.id for i in items2}


@pytest.mark.asyncio
async def test_seed_from_config_room(db_session: AsyncSession):
    """Seed creates items for room type."""
    items = await seed_property_items_from_config(db_session, "room")
    # room type should have several PropertyDefs
    assert len(items) >= 5

    # Verify some known room properties exist
    names = {item.properties["property_name"] for item in items}
    assert "name" in names
    assert "number" in names


@pytest.mark.asyncio
async def test_seed_nonexistent_type(db_session: AsyncSession):
    """Seeding a type with no properties returns empty list."""
    items = await seed_property_items_from_config(db_session, "nonexistent_type")
    assert items == []


@pytest.mark.asyncio
async def test_property_metadata_from_registered_def(db_session: AsyncSession):
    """Property item captures metadata from registered PropertyDef."""
    # door/width is a registered property with unit and normalization
    prop, _ = await get_or_create_property_item(db_session, "door", "width")
    assert prop.properties["label"] == "Width"
    assert prop.properties["data_type"] == "number"
    assert prop.properties["unit"] == "in"


@pytest.mark.asyncio
async def test_get_property_items_empty_type(db_session: AsyncSession):
    """Query for type with no properties returns empty list."""
    items = await get_property_items_for_type(db_session, "door")
    assert items == []

    # Create one property
    await get_or_create_property_item(db_session, "door", "finish")

    # Now should have one
    items = await get_property_items_for_type(db_session, "door")
    assert len(items) == 1


@pytest.mark.asyncio
async def test_multiple_connections_same_property(db_session: AsyncSession, make_item):
    """One property can connect to multiple instances."""
    prop, _ = await get_or_create_property_item(db_session, "door", "finish")
    door1 = await make_item("door", "Door 101")
    door2 = await make_item("door", "Door 102")

    await ensure_property_connection(db_session, prop, door1)
    await ensure_property_connection(db_session, prop, door2)

    # Verify both connections
    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == prop.id,
        )
    )
    conns = result.scalars().all()
    assert len(conns) == 2

    target_ids = {c.target_item_id for c in conns}
    assert door1.id in target_ids
    assert door2.id in target_ids
