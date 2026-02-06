"""Navigation API routes — WP-4: Bounce-back navigation with breadcrumb tracking."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.core import Connection, Item

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
    Check if two items are connected in either direction.

    A connection exists if:
    - item_a → item_b (outgoing from a to b)
    - item_b → item_a (incoming to a from b)
    """
    result = await db.execute(
        select(Connection).where(
            or_(
                and_(Connection.source_item_id == item_a_id, Connection.target_item_id == item_b_id),
                and_(Connection.source_item_id == item_b_id, Connection.target_item_id == item_a_id),
            )
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _item_exists(db: AsyncSession, item_id: uuid.UUID) -> bool:
    """Check if an item exists in the database."""
    result = await db.execute(
        select(Item).where(Item.id == item_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


# ─── Navigation Endpoint ───────────────────────────────────────────

@router.post("/navigate", response_model=NavigateResponse)
async def navigate(
    request: NavigateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Navigate with bounce-back algorithm.

    Given a breadcrumb path and a target item, compute the new breadcrumb:

    1. If target is already in breadcrumb, pop breadcrumb to the target (treat as sibling)
    2. If target is directly connected to the current item (last in breadcrumb)
       AND target is not already in breadcrumb → push (append target)
    3. Otherwise, walk backward through breadcrumb ancestors
    4. Find the most recent ancestor connected to target
    5. Pop breadcrumb to that ancestor, push target
    6. If no ancestor connects to target → return error with "no_path" status

    Per Decision 4: "connected" means a Connection row exists in EITHER direction.
    """

    # Validate inputs
    if not request.breadcrumb:
        raise HTTPException(status_code=400, detail="Breadcrumb cannot be empty")

    # Validate that all items in breadcrumb exist
    for item_id in request.breadcrumb:
        if not await _item_exists(db, item_id):
            raise HTTPException(
                status_code=404,
                detail=f"Item in breadcrumb not found: {item_id}",
            )

    # Validate target exists
    if not await _item_exists(db, request.target):
        raise HTTPException(status_code=404, detail="Target item not found")

    current_item = request.breadcrumb[-1]

    # Early exit: if target is already in breadcrumb, pop to it
    if request.target in request.breadcrumb:
        # Find the index of the target in the breadcrumb
        target_index = request.breadcrumb.index(request.target)
        # Pop breadcrumb to (and including) the target
        new_breadcrumb = request.breadcrumb[:target_index + 1]
        return NavigateResponse(
            breadcrumb=new_breadcrumb,
            action="bounce_back",
            bounced_from=None,
        )

    # Step 1: Check if target is directly connected to current item
    if await _is_connected(db, current_item, request.target):
        # Push: append target to breadcrumb
        new_breadcrumb = request.breadcrumb + [request.target]
        return NavigateResponse(
            breadcrumb=new_breadcrumb,
            action="push",
            bounced_from=None,
        )

    # Step 2: Walk backward through breadcrumb, looking for a connected ancestor
    # Start from second-to-last item and walk backwards
    for i in range(len(request.breadcrumb) - 2, -1, -1):
        ancestor_item = request.breadcrumb[i]

        if await _is_connected(db, ancestor_item, request.target):
            # Found a connected ancestor: pop breadcrumb to this ancestor and push target
            new_breadcrumb = request.breadcrumb[:i + 1] + [request.target]
            bounced_from = request.breadcrumb[i + 1] if i + 1 < len(request.breadcrumb) else None

            return NavigateResponse(
                breadcrumb=new_breadcrumb,
                action="bounce_back",
                bounced_from=bounced_from,
            )

    # Step 3: No ancestor connects to target
    return NavigateResponse(
        breadcrumb=request.breadcrumb,
        action="no_path",
        bounced_from=None,
    )
