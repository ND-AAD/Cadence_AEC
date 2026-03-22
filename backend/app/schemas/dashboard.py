"""
Dashboard and rollup schemas — WP-13a.

Response models for project health, import summaries,
action item rollups, and temporal trends.
"""

import uuid

from pydantic import BaseModel, Field


# ─── Project Health ──────────────────────────────────────────


class ActionItemCounts(BaseModel):
    """Counts of action items by status category."""

    unresolved_changes: int = 0
    unresolved_conflicts: int = 0
    pending_directives: int = 0
    fulfilled_directives: int = 0
    decisions_made: int = 0


class PropertyBreakdown(BaseModel):
    """Action item counts for a single property."""

    changes: int = 0
    conflicts: int = 0
    directives: int = 0


class SourcePairBreakdown(BaseModel):
    """Conflict counts for a specific source pair."""

    conflicts: int = 0


class AffectedTypeBreakdown(BaseModel):
    """Action item counts for items of a specific type."""

    changes: int = 0
    conflicts: int = 0
    directives: int = 0


class ProjectHealthResponse(BaseModel):
    """
    Project-level health summary.

    GET /api/v1/dashboard/health?project=uuid
    """

    total_items: int = 0
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description='Item counts by type: {"door": 50, "conflict": 10, ...}',
    )
    action_items: ActionItemCounts = Field(default_factory=ActionItemCounts)
    by_property: dict[str, PropertyBreakdown] = Field(
        default_factory=dict,
        description='Action item breakdown by property: {"finish": {changes: 5, ...}}',
    )
    by_source_pair: dict[str, SourcePairBreakdown] = Field(
        default_factory=dict,
        description='Conflict counts by source pair: {"Schedule+Spec": {conflicts: 8}}',
    )
    by_affected_type: dict[str, AffectedTypeBreakdown] = Field(
        default_factory=dict,
        description='Action item breakdown by affected item type: {"door": {"changes": 15, "conflicts": 8, "directives": 3}}',
    )


# ─── Import Summary ─────────────────────────────────────────


class SourceImportDetail(BaseModel):
    """Per-source breakdown within an import summary."""

    source_id: uuid.UUID
    source_identifier: str | None = None
    source_type: str | None = None
    changes: int = 0
    affected_items: int = 0
    conflicts: int = 0


class ImportSummaryResponse(BaseModel):
    """
    Most recent import results for the project.

    GET /api/v1/dashboard/import-summary?project=uuid
    """

    batch_id: uuid.UUID | None = None
    batch_identifier: str | None = None
    source_id: uuid.UUID | None = None
    source_identifier: str | None = None
    context_id: uuid.UUID | None = None
    context_identifier: str | None = None
    imported_at: str | None = None
    source_changes: int = 0
    affected_items: int = 0
    new_conflicts: int = 0
    resolved_conflicts: int = 0
    directives_fulfilled: int = 0
    items_imported: int = 0
    by_source: list[SourceImportDetail] = Field(default_factory=list)


# ─── Temporal Trend ──────────────────────────────────────────


class MilestoneTrend(BaseModel):
    """Action item counts at a single milestone."""

    context_id: uuid.UUID
    context_identifier: str | None = None
    ordinal: int = 0
    changes: int = 0
    conflicts: int = 0
    directives: int = 0
    resolved_conflicts: int = 0
    fulfilled_directives: int = 0


class TemporalTrendResponse(BaseModel):
    """
    Action item counts at each milestone over time.

    GET /api/v1/dashboard/temporal-trend?project=uuid
    """

    milestones: list[MilestoneTrend] = Field(default_factory=list)


# ─── Directive Status Rollup ─────────────────────────────────


class SourceDirectiveRollup(BaseModel):
    """Directive status for a single target source."""

    source_id: uuid.UUID
    source_identifier: str | None = None
    pending: int = 0
    fulfilled: int = 0


class DirectiveStatusResponse(BaseModel):
    """
    Directive status grouped by target source.

    GET /api/v1/dashboard/directive-status?project=uuid
    """

    total_pending: int = 0
    total_fulfilled: int = 0
    by_source: list[SourceDirectiveRollup] = Field(default_factory=list)


# ─── Affected Items (Workflow Perspective) ────────────────


class ItemActionCounts(BaseModel):
    """Per-item action counts for workflow categories."""

    changes: int = 0
    conflicts: int = 0
    directives: int = 0


class AffectedItemSummary(BaseModel):
    """Summary of an item with its action counts."""

    id: uuid.UUID
    identifier: str | None = None
    item_type: str
    action_counts: ItemActionCounts


class AffectedItemGroup(BaseModel):
    """Group of affected items by type."""

    item_type: str
    label: str
    count: int
    items: list[AffectedItemSummary]


class AffectedItemsResponse(BaseModel):
    """
    Response for affected items endpoint.

    GET /api/v1/dashboard/affected-items?project=uuid
    """

    groups: list[AffectedItemGroup] = Field(default_factory=list)
