"""Pydantic schemas for the Import Pipeline — WP-6."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Import Mapping Configuration ─────────────────────────────

class ImportMappingConfig(BaseModel):
    """
    Column-to-property mapping stored on the source item.

    The system normalizes standard patterns (case, whitespace, dimensions);
    the user configures non-obvious column-to-property mappings here.
    Once configured for the first import, subsequent imports from the
    same source reuse it.
    """
    file_type: str = Field(
        "excel",
        description="File format: 'excel' or 'csv'",
    )
    identifier_column: str = Field(
        ...,
        description="Column name containing item identifiers (e.g., 'DOOR NO.')",
    )
    target_item_type: str = Field(
        ...,
        description="Type of items being imported (e.g., 'door')",
    )
    header_row: int = Field(
        1,
        ge=1,
        description="1-indexed row number containing headers",
    )
    property_mapping: dict[str, str] = Field(
        ...,
        description="Mapping of column_name → property_name",
    )
    normalizations: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of property_name → normalization_type "
                    "(e.g., 'lowercase_trim', 'imperial_door_dimensions', 'numeric')",
    )


# ─── Import Request / Response ────────────────────────────────

class ImportRequest(BaseModel):
    """
    Request body for the main import endpoint.

    The file is uploaded separately as form data; this schema
    covers the JSON metadata that accompanies it.
    """
    source_item_id: uuid.UUID = Field(
        ...,
        description="The source item (schedule, spec, etc.)",
    )
    time_context_id: uuid.UUID = Field(
        ...,
        description="The milestone to import at (must have isTemporal/is_context_type)",
    )
    mapping_config: ImportMappingConfig | None = Field(
        None,
        description="Optional mapping config. If omitted, uses config stored on source item.",
    )


class MatchCandidate(BaseModel):
    """A fuzzy-match candidate for user confirmation."""
    item_id: uuid.UUID
    identifier: str | None
    item_type: str
    similarity: float = Field(..., ge=0.0, le=1.0)


class UnmatchedRow(BaseModel):
    """A row that couldn't be matched exactly or by normalization."""
    row_number: int
    raw_identifier: str
    candidates: list[MatchCandidate] = Field(default_factory=list)


class ImportSummary(BaseModel):
    """Counts and metadata from an import operation."""
    items_imported: int = 0
    items_created: int = 0
    items_matched_exact: int = 0
    items_matched_normalized: int = 0
    items_unmatched: int = 0
    snapshots_created: int = 0
    snapshots_upserted: int = 0
    connections_created: int = 0
    connections_existing: int = 0
    source_changes: int = 0
    affected_items: int = 0
    new_conflicts: int = 0
    resolved_conflicts: int = 0
    directives_fulfilled: int = 0
    items_classified: int = 0
    property_items_created: int = 0


# ─── Change Detection ──────────────────────────────────────────


class ChangeItemResult(BaseModel):
    """Result of detecting a single change on an item."""
    change_item_id: uuid.UUID
    affected_item_id: uuid.UUID
    affected_item_identifier: str | None
    property_name: str
    old_value: str | None
    new_value: str | None
    from_context_id: uuid.UUID
    to_context_id: uuid.UUID


# ─── Conflict Detection ──────────────────────────────────────────


class ConflictItemResult(BaseModel):
    """Result of detecting a single conflict between sources."""
    conflict_item_id: uuid.UUID
    affected_item_id: uuid.UUID
    affected_item_identifier: str | None
    property_name: str
    values: dict[str, str | None]  # source_identifier → value
    context_id: uuid.UUID


class ClassificationItemResult(BaseModel):
    """Result of classifying an element into a MasterFormat Division."""
    item_id: uuid.UUID
    item_identifier: str | None
    section_id: uuid.UUID
    section_identifier: str         # e.g., "08"
    section_title: str              # e.g., "Openings"
    confidence: str                 # "high", "medium", "low"
    needs_review: bool = False


class ImportResult(BaseModel):
    """Full response from the import endpoint."""
    batch_id: uuid.UUID
    source_item_id: uuid.UUID
    time_context_id: uuid.UUID
    summary: ImportSummary
    unmatched: list[UnmatchedRow] = Field(default_factory=list)
    change_items: list[ChangeItemResult] = Field(default_factory=list)
    conflict_items: list[ConflictItemResult] = Field(default_factory=list)
    classification_items: list[ClassificationItemResult] = Field(default_factory=list)


# ─── Batch / Confirm Endpoints ────────────────────────────────

class ConfirmMatchRequest(BaseModel):
    """Confirm a fuzzy match for an unmatched row."""
    raw_identifier: str
    matched_item_id: uuid.UUID


class ConfirmMatchResponse(BaseModel):
    """Result of confirming a match."""
    raw_identifier: str
    matched_item_id: uuid.UUID
    snapshot_created: bool
    connection_created: bool


# ─── Auto-Mapping Schemas (WP-6b) ───────────────────────────────

class ColumnProposalResponse(BaseModel):
    """Proposed mapping for a single column (API response)."""
    column_name: str
    proposed_property: str | None = None
    confidence: float = 0.0
    match_method: str = "none"
    alternatives: list[str] = Field(default_factory=list)


class ProposedMappingResponse(BaseModel):
    """Complete auto-mapping proposal (API response)."""
    proposal_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique ID for this proposal (used in confirm endpoint)",
    )
    header_row: int
    header_row_confidence: float
    target_item_type: str
    type_confidence: float
    identifier_column: str
    identifier_confidence: float
    columns: list[ColumnProposalResponse] = Field(default_factory=list)
    unmatched_columns: list[str] = Field(default_factory=list)
    proposed_config: ImportMappingConfig | None = None
    overall_confidence: float = 0.0
    needs_user_review: bool = True


class MappingCorrectionRequest(BaseModel):
    """User corrections to a proposed mapping."""
    corrections: dict[str, str | None] = Field(
        ...,
        description="Mapping of column_name → corrected property name (or None to skip)",
    )
    identifier_column: str | None = Field(
        None,
        description="Override identifier column if auto-detection was wrong",
    )
    target_item_type: str | None = Field(
        None,
        description="Override target item type if auto-detection was wrong",
    )
    header_row: int | None = Field(
        None,
        ge=1,
        description="Override header row if auto-detection was wrong",
    )


class MappingConfirmResponse(BaseModel):
    """Response after confirming/correcting a mapping."""
    confirmed_config: ImportMappingConfig
    corrections_saved: int = 0
    message: str = "Mapping confirmed"
