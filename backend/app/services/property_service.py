"""
Property item service.

Manages property definition items — the graph representation of property
concepts like "fire_rating" or "finish" scoped to a parent item type.

Property items are NOT value carriers (values live in snapshot JSONB).
They represent the concept itself, enabling navigation, rollup, and
MasterFormat governance connections.
"""

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.type_config import get_type_config
from app.models.core import Connection, Item


async def get_or_create_property_item(
    db: AsyncSession,
    parent_type: str,
    property_name: str,
) -> tuple[Item, bool]:
    """
    Get or create a property definition item.

    Lookup by identifier "{parent_type}/{property_name}".
    Populates metadata from PropertyDef if registered on the parent type.
    Falls back to title-cased label if no PropertyDef exists.

    Returns (item, is_new).
    """
    identifier = f"{parent_type}/{property_name}"

    # Check for existing
    result = await db.execute(
        select(Item).where(
            and_(
                Item.item_type == "property",
                Item.identifier == identifier,
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False

    # Resolve metadata from type config
    label = property_name.replace("_", " ").title()
    data_type = "string"
    unit = None

    tc = get_type_config(parent_type)
    if tc and tc.properties:
        for prop_def in tc.properties:
            if prop_def.name == property_name:
                label = prop_def.label
                data_type = prop_def.data_type
                unit = prop_def.unit
                break

    # Create property item
    prop_item = Item(
        item_type="property",
        identifier=identifier,
        properties={
            "property_name": property_name,
            "parent_type": parent_type,
            "label": label,
            "data_type": data_type,
            "unit": unit,
        },
    )
    db.add(prop_item)
    await db.flush()
    await db.refresh(prop_item)
    return prop_item, True


async def ensure_property_connection(
    db: AsyncSession,
    property_item: Item,
    instance_item: Item,
) -> bool:
    """
    Ensure connection exists: property_item → instance_item.

    Direction: property (source) → instance (target).
    Idempotent — returns False if connection already existed.
    """
    result = await db.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id == property_item.id,
                Connection.target_item_id == instance_item.id,
            )
        )
    )
    if result.scalar_one_or_none():
        return False

    db.add(Connection(
        source_item_id=property_item.id,
        target_item_id=instance_item.id,
        properties={},
    ))
    await db.flush()
    return True


async def get_property_items_for_type(
    db: AsyncSession,
    parent_type: str,
) -> list[Item]:
    """
    Get all property items for a given parent type.
    Matches by identifier prefix "{parent_type}/".
    """
    result = await db.execute(
        select(Item).where(
            and_(
                Item.item_type == "property",
                Item.identifier.like(f"{parent_type}/%"),
            )
        )
    )
    return list(result.scalars().all())


async def seed_property_items_from_config(
    db: AsyncSession,
    parent_type: str,
) -> list[Item]:
    """
    Create property items for all PropertyDefs registered on a type.
    Idempotent — skips existing items.
    Returns list of ALL property items for this type (new + existing).
    """
    tc = get_type_config(parent_type)
    if not tc or not tc.properties:
        return []

    items = []
    for prop_def in tc.properties:
        prop_item, _ = await get_or_create_property_item(
            db, parent_type, prop_def.name
        )
        items.append(prop_item)

    return items
