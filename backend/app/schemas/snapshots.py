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
    properties: dict = Field(
        default_factory=dict, description="Asserted property values"
    )


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


class PropertyWorkflowRefs(BaseModel):
    """
    Navigation handles for workflow items connected to a property.

    This is navigational metadata — it tells the frontend where to GO,
    not what the property looks like. Kept structurally separate from
    PropertyResolution's core fields (property_name, status, value, sources)
    which are about what the property IS.
    """

    conflict_id: uuid.UUID | None = None
    change_ids: list[uuid.UUID] = Field(default_factory=list)
    decision_id: uuid.UUID | None = None
    directive_ids: list[uuid.UUID] = Field(default_factory=list)
    resolution_metadata: dict | None = (
        None  # { decided_by, resolved_at, method, rationale, chosen_source }
    )


class PropertyResolution(BaseModel):
    """Resolution status for a single property across sources."""

    property_name: str
    status: str  # "agreed", "single_source", "conflicted", "resolved"
    value: str | int | float | bool | None = None  # Agreed/resolved value
    sources: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="source_identifier → value for each source",
    )
    effective_context: str | None = Field(
        default=None,
        description="Milestone identifier where the effective value originated. Null when the value was submitted at the requested context.",
    )
    workflow: PropertyWorkflowRefs | None = None


class ResolvedView(BaseModel):
    """
    The resolved view of an item at a specific context.

    For each property, shows whether sources agree, disagree,
    or only one source has spoken.
    """

    item: ItemSummary
    context: ItemSummary | None = None  # None when mode=current
    mode: str = "cumulative"  # "cumulative", "submitted", "current"
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
