"""Pydantic schemas for Specification Propagation — WP-18.2."""

import uuid

from pydantic import BaseModel, Field


# ─── Propagation Request / Response ──────────────────────────


class PropagateRequest(BaseModel):
    """Request body for propagation endpoint."""
    batch_id: uuid.UUID = Field(
        ...,
        description="UUID of the confirmed extraction_batch to propagate.",
    )


class PropagationSummary(BaseModel):
    """Aggregate counts from a propagation run."""
    batch_id: uuid.UUID
    status: str = "propagated"
    section_snapshots_created: int = 0
    element_snapshots_created: int = 0
    element_snapshots_updated: int = 0
    conditionals_deferred: int = 0
    conflicts_detected: int = 0
    conflicts_auto_resolved: int = 0
    directives_fulfilled: int = 0
    discovered_entities: int = 0


class PropagateResponse(BaseModel):
    """Response body for propagation endpoint."""
    summary: PropagationSummary
    message: str = "Extraction results propagated to graph."


# ─── Conditional Assignment ──────────────────────────────────


class ConditionalAssertion(BaseModel):
    """A single conditional assertion from extraction."""
    value: str
    condition: str


class PendingAssignment(BaseModel):
    """An element property needing user assignment."""
    element_id: uuid.UUID
    element_identifier: str | None
    property_name: str
    assertions: list[ConditionalAssertion]
    section_number: str
    section_item_id: uuid.UUID | None


class PendingAssignmentsResponse(BaseModel):
    """Response listing all pending conditional assignments."""
    batch_id: uuid.UUID
    assignments: list[PendingAssignment] = Field(default_factory=list)
    total: int = 0


class AssignmentItem(BaseModel):
    """A single assignment decision by the user."""
    element_ids: list[uuid.UUID] = Field(
        ...,
        description="Elements to apply this value to.",
    )
    property_name: str = Field(
        ...,
        description="The property to assign.",
    )
    value: str = Field(
        ...,
        description="The concrete value to assign.",
    )
    source_condition: str | None = Field(
        None,
        description="Which condition this value applies to (for audit trail).",
    )
    section_item_id: uuid.UUID = Field(
        ...,
        description="The spec section providing the assertion.",
    )


class AssignConditionalRequest(BaseModel):
    """Request body for assigning conditional values."""
    batch_id: uuid.UUID = Field(
        ...,
        description="The extraction batch these assignments apply to.",
    )
    assignments: list[AssignmentItem] = Field(
        ...,
        description="List of assignment decisions.",
    )


class AssignConditionalResponse(BaseModel):
    """Response from assigning conditional values."""
    assignments_made: int = 0
    conflicts_detected: int = 0
    message: str = "Conditional values assigned."
