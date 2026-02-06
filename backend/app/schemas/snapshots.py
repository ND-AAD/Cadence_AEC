"""Pydantic schemas for Snapshots — WP-5."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.items import ItemSummary


class SnapshotCreate(BaseModel):
    """Schema for creating a snapshot (or upserting on the triple)."""
    item_id: uuid.UUID = Field(..., description="WHAT: the item being described")
    context_id: uuid.UUID = Field(..., description="WHEN: the milestone context")
    source_id: uuid.UUID = Field(..., description="WHO SAYS: the asserting source")
    properties: dict = Field(default_factory=dict, description="Asserted property values")


class SnapshotResponse(BaseModel):
    """Schema for snapshot in API responses."""
    id: uuid.UUID
    item_id: uuid.UUID
    context_id: uuid.UUID
    source_id: uuid.UUID
    properties: dict
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SnapshotDetail(BaseModel):
    """Snapshot with expanded item references."""
    id: uuid.UUID
    item: ItemSummary
    context: ItemSummary
    source: ItemSummary
    properties: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Resolved View ────────────────────────────────────────────

class PropertyResolution(BaseModel):
    """Resolution status for a single property across sources."""
    property_name: str
    status: str  # "agreed", "single_source", "conflicted", "resolved"
    value: str | int | float | bool | None = None  # Agreed/resolved value
    sources: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="source_identifier → value for each source",
    )


class ResolvedView(BaseModel):
    """
    The resolved view of an item at a specific context.

    For each property, shows whether sources agree, disagree,
    or only one source has spoken.
    """
    item: ItemSummary
    context: ItemSummary
    properties: list[PropertyResolution]
    source_count: int
    snapshot_count: int


# ─── Effective Value ───────────────────────────────────────────

class EffectiveValue(BaseModel):
    """The effective (most recent by milestone ordinal) value from a source."""
    properties: dict
    as_of_context: ItemSummary
    source: ItemSummary
    snapshot_created_at: datetime
