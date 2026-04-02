"""Items API routes — WP-2: Full CRUD with search, validation, connected items."""

import re
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_for_item, require_project_access
from app.core.database import get_db
from app.core.type_config import ITEM_TYPES, get_type_config
from app.services.dynamic_types import resolve_user_firm, get_merged_registry
from app.models.core import Connection, Item, Snapshot
from app.models.infrastructure import Permission, User
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


def _natural_sort_key(s: str) -> list[tuple[int, int | str]]:
    """Split a string into text and numeric segments for natural ordering.
    "Door 2" → [(1, "door "), (0, 2)], "Door 101" → [(1, "door "), (0, 101)].
    Each segment is a (type_tag, value) tuple so mixed types never compare directly.
    Numbers sort before text at the same position (type_tag 0 < 1)."""
    parts: list[tuple[int, int | str]] = []
    for segment in re.split(r"(\d+)", s):
        if segment.isdigit():
            parts.append((0, int(segment)))
        else:
            parts.append((1, segment.lower()))
    return parts


# ─── CRUD ──────────────────────────────────────────────────────


@router.post("/", response_model=ItemResponse, status_code=201)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new item. Type must be registered in OS config or firm vocabulary."""
    # Check OS types first (fast path), then fall back to merged registry
    if payload.item_type not in ITEM_TYPES:
        firm = await resolve_user_firm(db, current_user.id)
        merged = await get_merged_registry(db, firm.id)
        if payload.item_type not in merged:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown item type: {payload.item_type}. "
                f"Valid types: {list(merged.keys())}",
            )

    item = Item(
        item_type=payload.item_type,
        identifier=payload.identifier,
        properties=payload.properties,
        created_by=current_user.id,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    # Auto-create admin permission when creating a project
    if payload.item_type == "project":
        permission = Permission(
            user_id=current_user.id,
            scope_item_id=item.id,
            role="admin",
            can_resolve_conflicts=True,
            can_import=True,
            can_edit=True,
        )
        db.add(permission)
        await db.flush()

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
            "render_mode": cfg.render_mode,
            "default_sort": cfg.default_sort,
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
    project: uuid.UUID | None = Query(
        None, description="Filter by project (connected ancestor)"
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    # Permission filter: when listing projects, scope to user's permissions
    if item_type == "project":
        accessible_projects = (
            select(Permission.scope_item_id)
            .where(Permission.user_id == current_user.id)
            .scalar_subquery()
        )
        query = query.where(Item.id.in_(accessible_projects))
        count_query = count_query.where(Item.id.in_(accessible_projects))

    # When listing non-project items without an explicit project filter,
    # scope to items within the user's accessible projects or created by them.
    if item_type != "project" and not project:
        accessible_projects = (
            select(Permission.scope_item_id)
            .where(Permission.user_id == current_user.id)
            .scalar_subquery()
        )
        direct_children = (
            select(Connection.target_item_id)
            .where(Connection.source_item_id.in_(accessible_projects))
            .scalar_subquery()
        )
        grandchildren = (
            select(Connection.target_item_id)
            .where(Connection.source_item_id.in_(direct_children))
            .scalar_subquery()
        )
        scope_filter = or_(
            Item.id.in_(accessible_projects),
            Item.id.in_(direct_children),
            Item.id.in_(grandchildren),
            Item.created_by == current_user.id,
        )
        query = query.where(scope_filter)
        count_query = count_query.where(scope_filter)

    # Trigram search on identifier
    if search:
        normalized = normalize_identifier(search)
        # Use trigram similarity — index idx_items_identifier_trgm handles this
        similarity_filter = (
            func.similarity(func.lower(Item.identifier), normalized) > 0.1
        )
        query = query.where(Item.identifier.isnot(None)).where(similarity_filter)
        count_query = count_query.where(Item.identifier.isnot(None)).where(
            similarity_filter
        )
        # Order by similarity descending for search results
        query = query.order_by(
            func.similarity(func.lower(Item.identifier), normalized).desc()
        )
    else:
        query = query.order_by(Item.created_at.desc())

    # Project filter: items connected (directly) to a project item
    if project:
        project_connected = (
            select(Connection.target_item_id)
            .where(Connection.source_item_id == project)
            .scalar_subquery()
        )
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
    current_user: User = Depends(get_current_user),
):
    """Get a single item by ID."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check project access
    project_id = await get_project_for_item(db, item_id)
    if project_id:
        await require_project_access(db, project_id, current_user)

    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    # Check project access
    project_id = await get_project_for_item(db, item_id)
    if project_id:
        await require_project_access(db, project_id, current_user)

    if payload.identifier is not None:
        item.identifier = payload.identifier
    if payload.properties is not None:
        merged = {**item.properties, **payload.properties}
        item.properties = merged

    if not item.created_by:
        item.created_by = current_user.id

    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an item and its connections."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check project access
    project_id = await get_project_for_item(db, item_id)
    if project_id:
        await require_project_access(db, project_id, current_user)

    # Delete connections referencing this item (both directions).
    await db.execute(
        Connection.__table__.delete().where(
            or_(
                Connection.source_item_id == item_id,
                Connection.target_item_id == item_id,
            )
        )
    )
    # Delete snapshots referencing this item.
    await db.execute(Snapshot.__table__.delete().where(Snapshot.item_id == item_id))
    # Delete the item itself via raw SQL to avoid ORM stale-state issues.
    await db.execute(Item.__table__.delete().where(Item.id == item_id))


@router.delete("/{item_id}/cascade", status_code=200)
async def delete_project_cascade(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a project and ALL items reachable from it.

    Walks the connection graph from the project outward, collecting every
    reachable item, then deletes all snapshots, connections, permissions,
    and items in that set. Alpha-only — no soft delete, no undo.
    """
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.item_type != "project":
        raise HTTPException(
            status_code=400, detail="Cascade delete is only for projects"
        )

    await require_project_access(db, item_id, current_user)

    # BFS to collect all reachable item IDs from the project
    visited: set[uuid.UUID] = {item_id}
    frontier: set[uuid.UUID] = {item_id}

    while frontier:
        outbound = await db.execute(
            select(Connection.target_item_id).where(
                Connection.source_item_id.in_(frontier)
            )
        )
        inbound = await db.execute(
            select(Connection.source_item_id).where(
                Connection.target_item_id.in_(frontier)
            )
        )
        neighbours = {r[0] for r in outbound.all()} | {r[0] for r in inbound.all()}
        neighbours -= visited
        visited |= neighbours
        frontier = neighbours

    # Delete in dependency order: snapshots → connections → permissions → items
    await db.execute(
        Snapshot.__table__.delete().where(
            or_(
                Snapshot.item_id.in_(visited),
                Snapshot.context_id.in_(visited),
                Snapshot.source_id.in_(visited),
            )
        )
    )
    await db.execute(
        Connection.__table__.delete().where(
            or_(
                Connection.source_item_id.in_(visited),
                Connection.target_item_id.in_(visited),
            )
        )
    )
    await db.execute(
        Permission.__table__.delete().where(Permission.scope_item_id == item_id)
    )
    await db.execute(Item.__table__.delete().where(Item.id.in_(visited)))

    return {"deleted_items": len(visited)}


# ─── Connected Items ───────────────────────────────────────────


@router.get("/{item_id}/connected", response_model=ConnectedItemsResponse)
async def get_connected_items(
    item_id: uuid.UUID,
    direction: str = Query(
        "both", description="Filter direction: outgoing, incoming, both"
    ),
    types: str | None = Query(None, description="Comma-separated type filter"),
    exclude: str | None = Query(
        None, description="Comma-separated UUIDs to exclude (breadcrumb ancestors)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    # Check project access
    project_id = await get_project_for_item(db, item_id)
    if project_id:
        await require_project_access(db, project_id, current_user)

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

    # For context types (milestones), also surface items via Snapshot.
    # When you navigate into "50% CD", you see items described at that
    # context and sources that submitted at it — same mechanism as
    # spatial navigation, just reading from the snapshot triple instead
    # of the connection table.
    type_cfg = get_type_config(item.item_type)
    if type_cfg and type_cfg.is_context_type:
        # Items described at this context (doors, rooms, etc.)
        snapshot_items_q = select(Item).where(
            Item.id.in_(
                select(Snapshot.item_id)
                .where(Snapshot.context_id == item_id)
                .distinct()
            )
        )
        if exclude_ids:
            snapshot_items_q = snapshot_items_q.where(Item.id.notin_(exclude_ids))
        if type_filter:
            snapshot_items_q = snapshot_items_q.where(Item.item_type.in_(type_filter))
        result = await db.execute(snapshot_items_q)
        connected_items.extend(result.scalars().all())

        # Sources that submitted at this context
        snapshot_sources_q = select(Item).where(
            Item.id.in_(
                select(Snapshot.source_id)
                .where(Snapshot.context_id == item_id)
                .distinct()
            )
        )
        if exclude_ids:
            snapshot_sources_q = snapshot_sources_q.where(Item.id.notin_(exclude_ids))
        if type_filter:
            snapshot_sources_q = snapshot_sources_q.where(
                Item.item_type.in_(type_filter)
            )
        result = await db.execute(snapshot_sources_q)
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
        action_result.scalar() or 0

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

    # Build ordinal lookup for temporal types (milestones, issuances).
    # Decision D7: milestone ordering uses ordinal property, not created_at.
    ordinal_lookup: dict[uuid.UUID, int] = {}
    for ci in unique_items:
        if ci.item_type in ("milestone", "issuance", "context"):
            ordinal = (ci.properties or {}).get("ordinal")
            if ordinal is not None:
                ordinal_lookup[ci.id] = int(ordinal)

    # Sort groups by type config order, items by ordinal (temporal) or identifier (others)
    groups = []
    for type_name, items_list in sorted(grouped.items()):
        type_cfg = get_type_config(type_name)
        if type_name in ("milestone", "issuance", "context"):
            # Temporal types: sort by ordinal, fall back to identifier
            items_list.sort(
                key=lambda x: (
                    ordinal_lookup.get(x.id, 999999),
                    (x.identifier or "").lower(),
                )
            )
        else:
            items_list.sort(key=lambda x: _natural_sort_key(x.identifier or ""))
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
