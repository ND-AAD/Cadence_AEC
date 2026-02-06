"""Items API routes — WP-2: Full CRUD with search, validation, connected items."""

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.type_config import ITEM_TYPES, get_type_config
from app.models.core import Connection, Item
from app.schemas.items import (
    ItemCreate,
    ItemResponse,
    ItemSummary,
    ItemUpdate,
    PaginatedItems,
    ConnectedItemsResponse,
    ConnectedGroup,
)
from app.services.normalization import normalize_identifier

router = APIRouter()


# ─── CRUD ──────────────────────────────────────────────────────

@router.post("/", response_model=ItemResponse, status_code=201)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new item. Type must be registered in configuration."""
    if payload.item_type not in ITEM_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown item type: {payload.item_type}. "
                   f"Valid types: {list(ITEM_TYPES.keys())}",
        )

    item = Item(
        item_type=payload.item_type,
        identifier=payload.identifier,
        properties=payload.properties,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.get("/types")
async def list_types():
    """List all registered item types and their configuration."""
    return {
        name: {
            "label": cfg.label,
            "plural_label": cfg.plural_label,
            "category": cfg.category,
            "icon": cfg.icon,
            "color": cfg.color,
            "navigable": cfg.navigable,
            "is_source_type": cfg.is_source_type,
            "is_context_type": cfg.is_context_type,
            "valid_targets": cfg.valid_targets,
            "properties": [
                {
                    "name": p.name,
                    "label": p.label,
                    "data_type": p.data_type,
                    "required": p.required,
                    "unit": p.unit,
                }
                for p in cfg.properties
            ],
        }
        for name, cfg in ITEM_TYPES.items()
    }


@router.get("/", response_model=PaginatedItems)
async def list_items(
    item_type: str | None = Query(None, description="Filter by item type"),
    search: str | None = Query(None, description="Search by identifier (trigram)"),
    project: uuid.UUID | None = Query(None, description="Filter by project (connected ancestor)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List items with filtering, search, and pagination.

    Search uses PostgreSQL pg_trgm for fuzzy matching on identifiers.
    """
    query = select(Item)
    count_query = select(func.count(Item.id))

    # Type filter
    if item_type:
        query = query.where(Item.item_type == item_type)
        count_query = count_query.where(Item.item_type == item_type)

    # Trigram search on identifier
    if search:
        normalized = normalize_identifier(search)
        # Use trigram similarity — index idx_items_identifier_trgm handles this
        similarity_filter = func.similarity(
            func.lower(Item.identifier), normalized
        ) > 0.1
        query = query.where(Item.identifier.isnot(None)).where(similarity_filter)
        count_query = count_query.where(Item.identifier.isnot(None)).where(similarity_filter)
        # Order by similarity descending for search results
        query = query.order_by(
            func.similarity(func.lower(Item.identifier), normalized).desc()
        )
    else:
        query = query.order_by(Item.created_at.desc())

    # Project filter: items connected (directly) to a project item
    if project:
        project_connected = select(Connection.target_item_id).where(
            Connection.source_item_id == project
        ).scalar_subquery()
        query = query.where(
            or_(
                Item.id == project,
                Item.id.in_(project_connected),
            )
        )
        count_query = count_query.where(
            or_(
                Item.id == project,
                Item.id.in_(project_connected),
            )
        )

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedItems(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single item by ID."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update an item's identifier or properties.

    Properties use merge semantics — provided keys are updated,
    existing keys not in the payload are preserved.
    """
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if payload.identifier is not None:
        item.identifier = payload.identifier
    if payload.properties is not None:
        merged = {**item.properties, **payload.properties}
        item.properties = merged

    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an item. Cascades to connections and snapshots."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)


# ─── Connected Items ───────────────────────────────────────────

@router.get("/{item_id}/connected", response_model=ConnectedItemsResponse)
async def get_connected_items(
    item_id: uuid.UUID,
    direction: str = Query("both", description="Filter direction: outgoing, incoming, both"),
    types: str | None = Query(None, description="Comma-separated type filter"),
    exclude: str | None = Query(None, description="Comma-separated UUIDs to exclude (breadcrumb ancestors)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get an item and its connected items, grouped by type.

    This is the primary navigation endpoint. Connected items are
    grouped by item_type for rendering in the UI. The exclude parameter
    filters out breadcrumb ancestors to prevent cycle visibility.

    Direction defaults to 'both' per Decision 4 — navigation queries
    traverse connections in both directions, relying on item types
    for semantic meaning.
    """
    # Get the item itself
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Parse exclusion list
    exclude_ids: set[uuid.UUID] = set()
    if exclude:
        for uid_str in exclude.split(","):
            try:
                exclude_ids.add(uuid.UUID(uid_str.strip()))
            except ValueError:
                pass

    # Parse type filter
    type_filter: set[str] | None = None
    if types:
        type_filter = {t.strip() for t in types.split(",")}

    # Build connected items query based on direction
    connected_items: list[Item] = []

    if direction in ("outgoing", "both"):
        q = (
            select(Item)
            .join(Connection, Connection.target_item_id == Item.id)
            .where(Connection.source_item_id == item_id)
        )
        if exclude_ids:
            q = q.where(Item.id.notin_(exclude_ids))
        if type_filter:
            q = q.where(Item.item_type.in_(type_filter))
        result = await db.execute(q)
        connected_items.extend(result.scalars().all())

    if direction in ("incoming", "both"):
        q = (
            select(Item)
            .join(Connection, Connection.source_item_id == Item.id)
            .where(Connection.target_item_id == item_id)
        )
        if exclude_ids:
            q = q.where(Item.id.notin_(exclude_ids))
        if type_filter:
            q = q.where(Item.item_type.in_(type_filter))
        result = await db.execute(q)
        connected_items.extend(result.scalars().all())

    # Deduplicate (item reachable via both directions)
    seen: set[uuid.UUID] = set()
    unique_items: list[Item] = []
    for ci in connected_items:
        if ci.id not in seen:
            seen.add(ci.id)
            unique_items.append(ci)

    # Group by type, calculating action counts for each connected item
    grouped: dict[str, list[ItemSummary]] = defaultdict(list)
    for ci in unique_items:
        # Count changes and conflicts connected to this item (as targets)
        action_counts_query = (
            select(func.count(Connection.id))
            .join(Item, Connection.source_item_id == Item.id)
            .where(Connection.target_item_id == ci.id)
            .where(Item.item_type.in_(["change", "conflict"]))
        )
        action_result = await db.execute(action_counts_query)
        action_count = action_result.scalar() or 0

        # Count both changes and conflicts separately for the action_counts dict
        changes_query = (
            select(func.count(Connection.id))
            .join(Item, Connection.source_item_id == Item.id)
            .where(Connection.target_item_id == ci.id)
            .where(Item.item_type == "change")
        )
        changes_result = await db.execute(changes_query)
        changes_count = changes_result.scalar() or 0

        conflicts_query = (
            select(func.count(Connection.id))
            .join(Item, Connection.source_item_id == Item.id)
            .where(Connection.target_item_id == ci.id)
            .where(Item.item_type == "conflict")
        )
        conflicts_result = await db.execute(conflicts_query)
        conflicts_count = conflicts_result.scalar() or 0

        grouped[ci.item_type].append(
            ItemSummary(
                id=ci.id,
                item_type=ci.item_type,
                identifier=ci.identifier,
                action_counts={"changes": changes_count, "conflicts": conflicts_count},
            )
        )

    # Sort groups by type config order, items by identifier within group
    groups = []
    for type_name, items_list in sorted(grouped.items()):
        type_cfg = get_type_config(type_name)
        items_list.sort(key=lambda x: (x.identifier or "").lower())
        groups.append(
            ConnectedGroup(
                item_type=type_name,
                label=type_cfg.plural_label if type_cfg else type_name,
                items=items_list,
                count=len(items_list),
            )
        )

    return ConnectedItemsResponse(
        item=ItemResponse.model_validate(item),
        connected=groups,
    )
