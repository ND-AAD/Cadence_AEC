"""Admin API routes — alpha-only utilities for testing and debugging."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.infrastructure import User

router = APIRouter()


@router.post("/reset-db", status_code=200)
async def reset_database(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Truncate all domain tables. Preserves users but clears everything else.

    Alpha-only — no confirmation, no undo. Wipes all items, connections,
    snapshots, permissions, and notifications.
    """
    await db.execute(text("TRUNCATE snapshots, connections, items CASCADE"))
    await db.execute(text("TRUNCATE permissions, notifications CASCADE"))

    return {
        "status": "reset",
        "message": "All domain data cleared. Users preserved.",
        "user": current_user.email,
    }
