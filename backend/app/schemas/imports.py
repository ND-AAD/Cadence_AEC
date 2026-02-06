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


class ImportResult(BaseModel):
    """Full response from the import endpoint."""
    batch_id: uuid.UUID
    source_item_id: uuid.UUID
    time_context_id: uuid.UUID
    summary: ImportSummary
    unmatched: list[UnmatchedRow] = Field(default_factory=list)
    change_items: list[ChangeItemResult] = Field(default_factory=list)
    conflict_items: list[ConflictItemResult] = Field(default_factory=list)


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
