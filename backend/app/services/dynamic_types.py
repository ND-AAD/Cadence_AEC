"""Dynamic type configuration service (WP-DYN-1)."""

import uuid

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Item, Connection
from app.models.infrastructure import Permission
from app.core.type_config import (
    TypeConfig,
    PropertyDef,
    ITEM_TYPES,
)


async def resolve_user_firm(db: AsyncSession, user_id: uuid.UUID) -> Item:
    """Find or create the user's firm item."""
    # Look for existing firm via Permission
    result = await db.execute(
        select(Item)
        .join(Permission, Permission.scope_item_id == Item.id)
        .where(
            Permission.user_id == user_id,
            Item.item_type == "firm",
        )
        .limit(1)
    )
    firm = result.scalar_one_or_none()
    if firm:
        return firm

    # Create firm + permission
    firm = Item(
        item_type="firm",
        identifier="My Firm",
        properties={"name": "My Firm"},
        created_by=user_id,
    )
    db.add(firm)
    await db.flush()
    await db.refresh(firm)

    perm = Permission(
        user_id=user_id,
        scope_item_id=firm.id,
        role="admin",
        can_resolve_conflicts=True,
        can_import=True,
        can_edit=True,
    )
    db.add(perm)
    await db.flush()

    return firm


def _item_to_type_config(item: Item) -> TypeConfig:
    """Convert a type_definition item to a TypeConfig."""
    props = item.properties or {}
    property_defs = []
    for pd in props.get("property_defs") or []:
        property_defs.append(
            PropertyDef(
                name=pd["name"],
                label=pd.get("label", pd["name"]),
                data_type=pd.get("data_type", "string"),
                required=pd.get("required", False),
                unit=pd.get("unit"),
                aliases=tuple(pd["aliases"]) if pd.get("aliases") else None,
                normalization=pd.get("normalization"),
                enum_values=pd.get("enum_values"),
            )
        )

    return TypeConfig(
        name=item.identifier,
        label=props.get("label", item.identifier),
        plural_label=props.get(
            "plural_label", f"{props.get('label', item.identifier)}s"
        ),
        category=props.get("category", "spatial"),
        navigable=props.get("navigable", True),
        is_source_type=props.get("is_source_type", False),
        is_context_type=props.get("is_context_type", False),
        render_mode=props.get("render_mode", "table"),
        exclude_from_conflicts=props.get("exclude_from_conflicts", False),
        search_fields=props.get("search_fields", []),
        masterformat_divisions=tuple(props.get("masterformat_divisions", ())),
        properties=property_defs,
        default_sort=props.get("default_sort", "identifier"),
        valid_targets=props.get("valid_targets", []),
    )


def _type_config_to_properties(tc: TypeConfig) -> dict:
    """Convert a TypeConfig to item properties dict (for storing as type_definition)."""
    return {
        "type_name": tc.name,
        "label": tc.label,
        "plural_label": tc.plural_label,
        "category": tc.category,
        "navigable": tc.navigable,
        "is_source_type": tc.is_source_type,
        "is_context_type": tc.is_context_type,
        "render_mode": tc.render_mode,
        "exclude_from_conflicts": tc.exclude_from_conflicts,
        "search_fields": tc.search_fields,
        "masterformat_divisions": list(tc.masterformat_divisions),
        "default_sort": tc.default_sort,
        "valid_targets": tc.valid_targets,
        "property_defs": [
            {
                "name": p.name,
                "label": p.label,
                "data_type": p.data_type,
                "required": p.required,
                "unit": p.unit,
                "aliases": list(p.aliases) if p.aliases else None,
                "normalization": p.normalization,
                "enum_values": p.enum_values,
            }
            for p in tc.properties
        ],
    }


async def get_firm_types(db: AsyncSession, firm_id: uuid.UUID) -> dict[str, TypeConfig]:
    """Load all type_definition items connected to a firm."""
    result = await db.execute(
        select(Item)
        .join(Connection, Connection.target_item_id == Item.id)
        .where(
            Connection.source_item_id == firm_id,
            Item.item_type == "type_definition",
        )
    )
    items = result.scalars().all()
    return {item.identifier: _item_to_type_config(item) for item in items}


async def get_merged_registry(
    db: AsyncSession, firm_id: uuid.UUID
) -> dict[str, TypeConfig]:
    """Merge OS types with firm types. OS types win on collision."""
    firm_types = await get_firm_types(db, firm_id)
    merged = dict(firm_types)  # Start with firm types
    merged.update(ITEM_TYPES)  # OS types overwrite any collisions
    return merged


async def create_type_definition(
    db: AsyncSession,
    firm_id: uuid.UUID,
    *,
    type_name: str,
    label: str,
    plural_label: str | None = None,
    property_defs: list[dict] | None = None,
    **kwargs,
) -> TypeConfig:
    """Create a new type definition connected to the firm."""
    # Reject OS type collision
    if type_name in ITEM_TYPES:
        raise ValueError(f"Cannot create '{type_name}': conflicts with OS type")

    # Reject duplicate within firm
    existing = await get_firm_types(db, firm_id)
    if type_name in existing:
        raise ValueError(f"Type '{type_name}' already exists for this firm")

    # Build properties dict
    props = {
        "type_name": type_name,
        "label": label,
        "plural_label": plural_label or f"{label}s",
        "category": kwargs.get("category", "spatial"),
        "navigable": kwargs.get("navigable", True),
        "is_source_type": kwargs.get("is_source_type", False),
        "is_context_type": kwargs.get("is_context_type", False),
        "render_mode": kwargs.get("render_mode", "table"),
        "exclude_from_conflicts": kwargs.get("exclude_from_conflicts", False),
        "search_fields": kwargs.get("search_fields", []),
        "masterformat_divisions": kwargs.get("masterformat_divisions", []),
        "default_sort": kwargs.get("default_sort", "identifier"),
        "valid_targets": kwargs.get("valid_targets", []),
        "property_defs": property_defs or [],
    }

    item = Item(
        item_type="type_definition",
        identifier=type_name,
        properties=props,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    # Connect to firm
    conn = Connection(
        source_item_id=firm_id,
        target_item_id=item.id,
    )
    db.add(conn)
    await db.flush()

    return _item_to_type_config(item)


async def update_type_definition(
    db: AsyncSession,
    firm_id: uuid.UUID,
    type_name: str,
    **kwargs,
) -> TypeConfig:
    """Update a firm type definition."""
    if type_name in ITEM_TYPES:
        raise ValueError(f"Cannot update '{type_name}': OS type is immutable")

    # Find the type_definition item
    result = await db.execute(
        select(Item)
        .join(Connection, Connection.target_item_id == Item.id)
        .where(
            Connection.source_item_id == firm_id,
            Item.item_type == "type_definition",
            Item.identifier == type_name,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError(f"Type '{type_name}' not found for this firm")

    # Update properties
    props = dict(item.properties or {})
    for key in (
        "label",
        "plural_label",
        "category",
        "render_mode",
        "search_fields",
        "property_defs",
        "navigable",
        "exclude_from_conflicts",
        "is_source_type",
        "is_context_type",
        "valid_targets",
        "masterformat_divisions",
        "default_sort",
    ):
        if key in kwargs:
            props[key] = kwargs[key]

    item.properties = props
    await db.flush()
    await db.refresh(item)

    return _item_to_type_config(item)


async def delete_type_definition(
    db: AsyncSession,
    firm_id: uuid.UUID,
    type_name: str,
) -> None:
    """Delete a firm type definition."""
    if type_name in ITEM_TYPES:
        raise ValueError(f"Cannot delete '{type_name}': OS type is immutable")

    # Find the type_definition item
    result = await db.execute(
        select(Item)
        .join(Connection, Connection.target_item_id == Item.id)
        .where(
            Connection.source_item_id == firm_id,
            Item.item_type == "type_definition",
            Item.identifier == type_name,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError(f"Type '{type_name}' not found for this firm")

    # Check for existing items of this type
    count_result = await db.execute(
        select(func.count()).select_from(Item).where(Item.item_type == type_name)
    )
    count = count_result.scalar()
    if count > 0:
        raise ValueError(
            f"Cannot delete '{type_name}': {count} items exist with this type"
        )

    # Delete connections to this item
    await db.execute(
        delete(Connection).where(
            (Connection.source_item_id == item.id)
            | (Connection.target_item_id == item.id)
        )
    )
    # Delete the item
    await db.execute(delete(Item).where(Item.id == item.id))
    await db.flush()


async def seed_firm_types(
    db: AsyncSession,
    firm_id: uuid.UUID,
) -> list[TypeConfig]:
    """Create starter catalog types for a firm. Skips types that already exist."""
    from app.core.type_starter_catalog import STARTER_TYPES

    existing = await get_firm_types(db, firm_id)
    seeded = []

    for tc in STARTER_TYPES:
        if tc.name in existing:
            continue

        props = _type_config_to_properties(tc)
        item = Item(
            item_type="type_definition",
            identifier=tc.name,
            properties=props,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)

        conn = Connection(
            source_item_id=firm_id,
            target_item_id=item.id,
        )
        db.add(conn)
        await db.flush()

        seeded.append(_item_to_type_config(item))

    return seeded
