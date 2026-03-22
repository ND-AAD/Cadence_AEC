"""
Resolution workflow schemas — WP-12a.

Request/response models for conflict resolution, change acknowledgment,
directive management, and action item queries.
"""

import uuid
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.items import ItemResponse


# ─── Enums ───────────────────────────────────────────────────

class ResolutionMethod(str, Enum):
    """How a conflict was resolved."""
    CHOSEN_SOURCE = "chosen_source"   # One source's value wins
    MANUAL_VALUE = "manual_value"     # User entered a custom value


# ─── Conflict Resolution ────────────────────────────────────

class ConflictResolveRequest(BaseModel):
    """Request to resolve a single conflict."""
    chosen_value: str | None = Field(
        None,
        description="Resolved value. Required for manual_value method.",
    )
    chosen_source_id: uuid.UUID | None = Field(
        None,
        description="Source whose value wins. Required for chosen_source method.",
    )
    method: ResolutionMethod = Field(
        ...,
        description="How the conflict was resolved.",
    )
    rationale: str = Field(
        ...,
        description="Why this resolution was chosen.",
    )
    decided_by: str = Field(
        ...,
        description="Name or identifier of who decided.",
    )


class ConflictResolveResponse(BaseModel):
    """Response after resolving a conflict."""
    decision_item: ItemResponse
    conflict_item_id: uuid.UUID
    conflict_updated: bool
    directives_created: int
    directives_fulfilled: int


# ─── Bulk Resolution ────────────────────────────────────────

class BulkResolveEntry(BaseModel):
    """One entry in a bulk resolve request."""
    conflict_item_id: uuid.UUID
    chosen_value: str | None = None
    chosen_source_id: uuid.UUID | None = None
    method: ResolutionMethod
    rationale: str
    decided_by: str


class BulkResolveRequest(BaseModel):
    """Batch resolve multiple conflicts."""
    resolutions: list[BulkResolveEntry]


class BulkResolveResult(BaseModel):
    """Result for one item in bulk resolve."""
    conflict_item_id: uuid.UUID
    success: bool
    error: str | None = None
    decision_item_id: uuid.UUID | None = None
    directives_created: int = 0


class BulkResolveResponse(BaseModel):
    """Response from bulk resolve endpoint."""
    total_attempted: int
    total_succeeded: int
    total_failed: int
    results: list[BulkResolveResult]


# ─── Change Acknowledgment ──────────────────────────────────

class ChangeAcknowledgeResponse(BaseModel):
    """Response after acknowledging a change."""
    change_item_id: uuid.UUID
    status: str = "acknowledged"


# ─── Directive Fulfillment ──────────────────────────────────

class DirectiveFulfillResponse(BaseModel):
    """Response after fulfilling a directive."""
    directive_item_id: uuid.UUID
    status: str = "fulfilled"


# ─── Action Items Query ─────────────────────────────────────

class ActionItemRollup(BaseModel):
    """Summary of pending action items across all types."""
    changes_pending: int = 0
    conflicts_pending: int = 0
    directives_pending: int = 0
    total_action_items: int = 0
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown: {changes: N, conflicts: N, directives: N}",
    )
    by_property: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description='Breakdown by property: {"finish": {"changes": 1, "conflicts": 2, "directives": 1}}',
    )


# ─── Directive Listing ──────────────────────────────────────

class DirectiveDetail(BaseModel):
    """A directive with expanded details."""
    id: uuid.UUID
    identifier: str | None
    property_name: str
    target_value: str | None
    target_source_id: uuid.UUID | None
    affected_item_id: uuid.UUID | None
    decision_item_id: uuid.UUID | None
    status: str
    created_at: str | None = None

    model_config = {"from_attributes": True}


class DirectiveListResponse(BaseModel):
    """List of directives matching criteria."""
    directives: list[DirectiveDetail]
    total: int
    pending_by_source: dict[str, int] = Field(
        default_factory=dict,
        description="Count of pending directives per target source UUID.",
    )


# ─── Status Transitions (Decision 13) ────────────────────

class StatusTransitionResponse(BaseModel):
    """Response after a workflow status transition (start-review, hold, resume-review)."""
    item_id: uuid.UUID
    item_type: str
    previous_status: str
    new_status: str
