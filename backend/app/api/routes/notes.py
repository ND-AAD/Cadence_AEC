"""Notes/Cairn CRUD endpoints.

Notes are items (type "note") connected to a target item via a connection.
They represent human-authored markers in the graph — cairns per DS-2 §5.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.core import Connection, Item

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────


class CreateNoteRequest(BaseModel):
    content: str = Field(..., min_length=1)
    author: str = Field(default="")


class NoteResponse(BaseModel):
    id: str
    content: str
    author: str
    item_id: str
    created_at: str


class NoteListResponse(BaseModel):
    notes: list[NoteResponse]


# ─── Helpers ──────────────────────────────────────────────────


def _note_to_response(note: Item, target_item_id: uuid.UUID) -> NoteResponse:
    return NoteResponse(
        id=str(note.id),
        content=note.properties.get("content", ""),
        author=note.properties.get("author", ""),
        item_id=str(target_item_id),
        created_at=note.created_at.isoformat() if note.created_at else "",
    )


# ─── Endpoints ────────────────────────────────────────────────


@router.post("/items/{item_id}/notes", response_model=NoteResponse, status_code=201)
async def create_note(
    item_id: uuid.UUID,
    payload: CreateNoteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a cairn (note item) connected to the target item."""
    # Verify target item exists
    result = await db.execute(select(Item).where(Item.id == item_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Item not found")

    # Create the note item
    note = Item(
        item_type="note",
        identifier=f"note-{uuid.uuid4().hex[:8]}",
        properties={
            "content": payload.content,
            "author": payload.author,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(note)
    await db.flush()

    # Connect note → target item
    conn = Connection(
        source_item_id=note.id,
        target_item_id=item_id,
        properties={},
    )
    db.add(conn)
    await db.flush()
    await db.refresh(note)

    return _note_to_response(note, item_id)


@router.get("/items/{item_id}/notes", response_model=NoteListResponse)
async def list_notes(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all cairns (notes) connected to an item, newest first."""
    # Find note items connected to this item (note → target).
    # Order newest first by created_at, then by identifier as tiebreaker.
    result = await db.execute(
        select(Item)
        .join(Connection, Connection.source_item_id == Item.id)
        .where(
            Connection.target_item_id == item_id,
            Item.item_type == "note",
        )
        .order_by(Item.created_at.desc(), Item.identifier.desc())
    )
    notes = result.scalars().all()

    return NoteListResponse(notes=[_note_to_response(n, item_id) for n in notes])
