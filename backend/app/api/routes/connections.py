"""Connections API routes — WP-2: Full CRUD with validation and soft disconnect."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.core import Connection, Item
from app.schemas.connections import (
    ConnectionCreate,
    ConnectionResponse,
    DisconnectRequest,
)

router = APIRouter()


@router.post("/", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    payload: ConnectionCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a directional connection between two items.

    Validates:
    - Both items exist
    - Self-connection prevention (handled by schema validator)
    - Duplicate connection prevention (same source -> target returns 409)
    """
    # Verify both items exist
    for item_id, label in [
        (payload.source_item_id, "source"),
        (payload.target_item_id, "target"),
    ]:
        result = await db.execute(select(Item.id).where(Item.id == item_id))
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=404,
                detail=f"{label.capitalize()} item not found: {item_id}",
            )

    # Check for duplicate connection (same direction)
    existing = await db.execute(
        select(Connection.id).where(
            and_(
                Connection.source_item_id == payload.source_item_id,
                Connection.target_item_id == payload.target_item_id,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Connection already exists between these items in this direction",
        )

    connection = Connection(
        source_item_id=payload.source_item_id,
        target_item_id=payload.target_item_id,
        properties=payload.properties,
    )
    db.add(connection)
    await db.flush()
    await db.refresh(connection)
    return connection


@router.get("/", response_model=list[ConnectionResponse])
async def list_connections(
    item_id: uuid.UUID | None = Query(None, description="Filter by item (source or target)"),
    source_item_id: uuid.UUID | None = Query(None, description="Filter by source item"),
    target_item_id: uuid.UUID | None = Query(None, description="Filter by target item"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List connections with optional filters."""
    query = select(Connection).order_by(Connection.created_at.desc())

    if item_id:
        query = query.where(
            or_(
                Connection.source_item_id == item_id,
                Connection.target_item_id == item_id,
            )
        )
    if source_item_id:
        query = query.where(Connection.source_item_id == source_item_id)
    if target_item_id:
        query = query.where(Connection.target_item_id == target_item_id)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/disconnect", response_model=ConnectionResponse)
async def disconnect(
    payload: DisconnectRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Soft disconnect: records the disconnection reason in properties
    rather than deleting the connection. Per spec principle:
    'Nothing is deleted, only the story grows.'

    Sets disconnected=true and records the reason and timestamp
    in the connection's properties.
    """
    result = await db.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id == payload.source_item_id,
                Connection.target_item_id == payload.target_item_id,
            )
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(
            status_code=404,
            detail="No connection found between these items in this direction",
        )

    # Record the disconnection in properties
    updated_props = {
        **connection.properties,
        "disconnected": True,
        "disconnected_at": datetime.now(timezone.utc).isoformat(),
    }
    if payload.reason:
        updated_props["disconnect_reason"] = payload.reason

    connection.properties = updated_props
    await db.flush()
    await db.refresh(connection)
    return connection


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Hard delete a connection. Use /disconnect for soft removal."""
    result = await db.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    await db.delete(connection)
