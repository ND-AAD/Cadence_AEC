"""Navigation API routes — WP-4: Bounce-back navigation with breadcrumb tracking."""

import uuid
from collections import deque
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_access, get_project_for_item
from app.core.database import get_db
from app.core.type_config import get_type_config
from app.models.core import Connection, Item, Snapshot
from app.models.infrastructure import User

router = APIRouter()


# ─── Schemas ───────────────────────────────────────────────────────


class NavigateRequest(BaseModel):
    """Request to navigate to a target item."""

    breadcrumb: list[uuid.UUID] = Field(
        ..., description="Current breadcrumb path (list of item IDs)"
    )
    target: uuid.UUID = Field(..., description="Target item UUID to navigate to")


class NavigateResponse(BaseModel):
    """Response with new breadcrumb after navigation."""

    breadcrumb: list[uuid.UUID]
    action: Literal["push", "bounce_back", "no_path"]
    bounced_from: uuid.UUID | None = None


# ─── Navigation Algorithm ──────────────────────────────────────────


async def _is_connected(
    db: AsyncSession,
    item_a_id: uuid.UUID,
    item_b_id: uuid.UUID,
) -> bool:
    """
    Check if two items are navigably adjacent.

    Adjacency means either:
    1. A Connection row exists between them (either direction), OR
    2. One item is a context type (is_context_type=true) and the other
       has a snapshot with context_id pointing to the context item.

    Case 2 aligns the navigate endpoint with the connected items
    endpoint (items.py get_connected_items), which already surfaces
    snapshot-described items for context types. If you can see it in
    the panel, you can navigate to it.
    """
    # Check 1: Connection table (bidirectional).
    conn_result = await db.execute(
        select(Connection.id)
        .where(
            or_(
                and_(
                    Connection.source_item_id == item_a_id,
                    Connection.target_item_id == item_b_id,
                ),
                and_(
                    Connection.source_item_id == item_b_id,
                    Connection.target_item_id == item_a_id,
                ),
            )
        )
        .limit(1)
    )
    if conn_result.scalar_one_or_none() is not None:
        return True

    # Check 2: Snapshot-based adjacency for context types.
    # Load both items' types to check is_context_type.
    a_result = await db.execute(select(Item.item_type).where(Item.id == item_a_id))
    a_type = a_result.scalar_one_or_none()
    b_result = await db.execute(select(Item.item_type).where(Item.id == item_b_id))
    b_type = b_result.scalar_one_or_none()

    if not a_type or not b_type:
        return False

    # item_a is context type: check if item_b is described at item_a
    # or is a source that submitted at item_a.
    a_cfg = get_type_config(a_type)
    if a_cfg and a_cfg.is_context_type:
        snap_result = await db.execute(
            select(Snapshot.id)
            .where(
                and_(
                    Snapshot.context_id == item_a_id,
                    or_(
                        Snapshot.item_id == item_b_id,
                        Snapshot.source_id == item_b_id,
                    ),
                )
            )
            .limit(1)
        )
        if snap_result.scalar_one_or_none() is not None:
            return True

    # item_b is context type: check if item_a is described at item_b
    # or is a source that submitted at item_b.
    b_cfg = get_type_config(b_type)
    if b_cfg and b_cfg.is_context_type:
        snap_result = await db.execute(
            select(Snapshot.id)
            .where(
                and_(
                    Snapshot.context_id == item_b_id,
                    or_(
                        Snapshot.item_id == item_a_id,
                        Snapshot.source_id == item_a_id,
                    ),
                )
            )
            .limit(1)
        )
        if snap_result.scalar_one_or_none() is not None:
            return True

    return False


async def _item_exists(db: AsyncSession, item_id: uuid.UUID) -> bool:
    """Check if an item exists in the database."""
    result = await db.execute(select(Item.id).where(Item.id == item_id).limit(1))
    return result.scalar_one_or_none() is not None


async def _get_neighbors(
    db: AsyncSession,
    item_id: uuid.UUID,
    exclude: set[uuid.UUID] | None = None,
) -> list[uuid.UUID]:
    """
    Get all navigably adjacent items for BFS traversal.

    Returns neighbors via both Connection rows and snapshot-based
    adjacency for context types, minus any items in the exclude set.
    """
    neighbors: set[uuid.UUID] = set()
    excl = exclude or set()

    # Connection-based neighbors (bidirectional).
    conn_result = await db.execute(
        select(Connection.source_item_id, Connection.target_item_id).where(
            or_(
                Connection.source_item_id == item_id,
                Connection.target_item_id == item_id,
            )
        )
    )
    for row in conn_result.all():
        neighbor = row[1] if row[0] == item_id else row[0]
        if neighbor not in excl:
            neighbors.add(neighbor)

    # Snapshot-based neighbors for context types.
    type_result = await db.execute(select(Item.item_type).where(Item.id == item_id))
    item_type = type_result.scalar_one_or_none()
    if item_type:
        cfg = get_type_config(item_type)
        if cfg and cfg.is_context_type:
            # Items described at this context.
            described = await db.execute(
                select(Snapshot.item_id)
                .where(Snapshot.context_id == item_id)
                .distinct()
            )
            for row in described.all():
                if row[0] not in excl:
                    neighbors.add(row[0])

            # Sources that submitted at this context.
            sources = await db.execute(
                select(Snapshot.source_id)
                .where(Snapshot.context_id == item_id)
                .distinct()
            )
            for row in sources.all():
                if row[0] not in excl:
                    neighbors.add(row[0])

    return list(neighbors)


async def _find_path_bfs(
    db: AsyncSession,
    start_id: uuid.UUID,
    target_id: uuid.UUID,
    breadcrumb_ids: set[uuid.UUID] | None = None,
    max_depth: int = 10,
) -> list[uuid.UUID] | None:
    """
    BFS through the navigable graph to find shortest path from start to target.

    Returns list of item IDs from start (exclusive) to target (inclusive),
    or None if no path found within max_depth.

    The breadcrumb_ids set excludes already-traversed items from the search
    to prevent routing through ancestors (which would violate the breadcrumb
    invariant: you cannot reach an ancestor without backtracking).
    """
    visited: set[uuid.UUID] = {start_id}
    if breadcrumb_ids:
        # Exclude all breadcrumb items except the start (already added)
        # and the target (which we're trying to reach).
        visited |= breadcrumb_ids - {start_id, target_id}

    queue: deque[tuple[uuid.UUID, list[uuid.UUID]]] = deque()
    queue.append((start_id, []))

    while queue:
        current_id, path = queue.popleft()

        if len(path) >= max_depth:
            continue

        neighbors = await _get_neighbors(db, current_id, exclude=visited)

        for neighbor_id in neighbors:
            new_path = path + [neighbor_id]

            if neighbor_id == target_id:
                return new_path

            visited.add(neighbor_id)
            queue.append((neighbor_id, new_path))

    return None


# ─── Navigation Endpoint ───────────────────────────────────────────


@router.post("/navigate", response_model=NavigateResponse)
async def navigate(
    request: NavigateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Navigate with bounce-back algorithm.

    Given a breadcrumb path and a target item, compute the new breadcrumb:

    1. If target is already in breadcrumb, pop breadcrumb to the target
    2. If target is directly connected to the current item (last in breadcrumb)
       AND target is not already in breadcrumb, push (append target)
    3. Otherwise, walk backward through breadcrumb ancestors
    4. Find the most recent ancestor connected to target
    5. Pop breadcrumb to that ancestor, push target
    6. BFS fallback (excludes breadcrumb items from traversal)
    7. If no path found, return "no_path"

    "Connected" means navigably adjacent: a Connection row in either
    direction, OR snapshot-based adjacency for context types. This
    matches the connected items endpoint so that if you can see an
    item in the panel, you can click it.
    """

    # Validate inputs
    if not request.breadcrumb:
        raise HTTPException(status_code=400, detail="Breadcrumb cannot be empty")

    for item_id in request.breadcrumb:
        if not await _item_exists(db, item_id):
            raise HTTPException(
                status_code=404,
                detail=f"Item in breadcrumb not found: {item_id}",
            )

    if not await _item_exists(db, request.target):
        raise HTTPException(status_code=404, detail="Target item not found")

    # Check project access via first breadcrumb item
    project_id = await get_project_for_item(db, request.breadcrumb[0])
    if project_id:
        await require_project_access(db, project_id, current_user)

    current_item = request.breadcrumb[-1]

    # Step 1: If target is already in breadcrumb, pop to it.
    if request.target in request.breadcrumb:
        target_index = request.breadcrumb.index(request.target)
        new_breadcrumb = request.breadcrumb[: target_index + 1]
        return NavigateResponse(
            breadcrumb=new_breadcrumb,
            action="bounce_back",
            bounced_from=None,
        )

    # Step 2: Check if target is directly connected to current item.
    if await _is_connected(db, current_item, request.target):
        new_breadcrumb = request.breadcrumb + [request.target]
        return NavigateResponse(
            breadcrumb=new_breadcrumb,
            action="push",
            bounced_from=None,
        )

    # Step 3: Walk backward through breadcrumb, looking for a connected ancestor.
    for i in range(len(request.breadcrumb) - 2, -1, -1):
        ancestor_item = request.breadcrumb[i]

        if await _is_connected(db, ancestor_item, request.target):
            new_breadcrumb = request.breadcrumb[: i + 1] + [request.target]
            bounced_from = (
                request.breadcrumb[i + 1] if i + 1 < len(request.breadcrumb) else None
            )

            return NavigateResponse(
                breadcrumb=new_breadcrumb,
                action="bounce_back",
                bounced_from=bounced_from,
            )

    # Step 4: BFS path-finding, excluding breadcrumb items from traversal.
    breadcrumb_set = set(request.breadcrumb)
    path = await _find_path_bfs(
        db,
        current_item,
        request.target,
        breadcrumb_ids=breadcrumb_set,
    )
    if path:
        new_breadcrumb = request.breadcrumb + path
        return NavigateResponse(
            breadcrumb=new_breadcrumb,
            action="push",
        )

    # Step 5: No path found.
    return NavigateResponse(
        breadcrumb=request.breadcrumb,
        action="no_path",
        bounced_from=None,
    )
