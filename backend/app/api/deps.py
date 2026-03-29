"""Shared dependencies for API routes."""

import uuid

from fastapi import Depends, HTTPException, Header
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token
from app.core.database import get_db
from app.models.core import Connection, Item
from app.models.infrastructure import Permission, User


async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_project_for_item(
    db: AsyncSession,
    item_id: uuid.UUID,
) -> uuid.UUID | None:
    """
    Walk the connection graph upward to find the project ancestor.

    Strategy: check if the item IS a project, then check direct
    parents, then check grandparents. Bounded to 3 hops -- Cadence's
    graph is shallow (project -> milestone/source -> door -> property).

    Returns the project UUID or None if no project ancestor found.
    """
    # Check if the item itself is a project
    result = await db.execute(
        select(Item.item_type).where(Item.id == item_id)
    )
    row = result.one_or_none()
    if not row:
        return None
    if row[0] == "project":
        return item_id

    # Check direct parents (items that connect TO this item)
    parents_result = await db.execute(
        select(Connection.source_item_id).where(
            Connection.target_item_id == item_id
        )
    )
    parent_ids = [r[0] for r in parents_result.all()]

    for pid in parent_ids:
        p_result = await db.execute(
            select(Item.item_type).where(Item.id == pid)
        )
        p_row = p_result.one_or_none()
        if p_row and p_row[0] == "project":
            return pid

    # Check grandparents (one more hop)
    for pid in parent_ids:
        gp_result = await db.execute(
            select(Connection.source_item_id).where(
                Connection.target_item_id == pid
            )
        )
        gp_ids = [r[0] for r in gp_result.all()]
        for gpid in gp_ids:
            gp_type = await db.execute(
                select(Item.item_type).where(Item.id == gpid)
            )
            gp_row = gp_type.one_or_none()
            if gp_row and gp_row[0] == "project":
                return gpid

    return None


async def require_project_access(
    db: AsyncSession,
    project_id: uuid.UUID,
    user: User,
) -> None:
    """
    Check that the user has a Permission row for this project.
    Raises 403 if not.

    For alpha, any Permission row is sufficient -- role-based
    enforcement is deferred.
    """
    result = await db.execute(
        select(Permission.id).where(
            and_(
                Permission.user_id == user.id,
                Permission.scope_item_id == project_id,
            )
        ).limit(1)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this project.",
        )
