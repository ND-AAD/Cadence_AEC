"""
Dashboard routes — WP-13a.

Read-only rollup and summary endpoints for project health,
import summaries, temporal trends, and directive status.

Endpoints:
  GET /dashboard/health           — project health summary
  GET /dashboard/import-summary   — most recent import results
  GET /dashboard/temporal-trend   — action item counts at each milestone
  GET /dashboard/directive-status — directive status by target source
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_access
from app.core.database import get_db
from app.models.infrastructure import User
from app.schemas.dashboard import (
    ActionItemCounts,
    AffectedItemGroup,
    AffectedItemsResponse,
    DirectiveStatusResponse,
    ImportSummaryResponse,
    ItemActionCounts,
    ProjectHealthResponse,
    PropertyBreakdown,
    SourceDirectiveRollup,
    SourcePairBreakdown,
    TemporalTrendResponse,
    MilestoneTrend,
)
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])


# ─── Project Health ──────────────────────────────────────────


@router.get(
    "/dashboard/health",
    response_model=ProjectHealthResponse,
    status_code=200,
)
async def get_project_health(
    project: uuid.UUID | None = Query(None, description="Project item ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Project-level health summary.

    Returns total item counts by type, action item breakdowns
    by property, source pair, and affected item type.
    """
    # Check project access if project provided
    if project:
        await require_project_access(db, project, current_user)

    data = await dashboard_service.get_project_health(db, project_id=project)

    return ProjectHealthResponse(
        total_items=data["total_items"],
        by_type=data["by_type"],
        action_items=ActionItemCounts(**data["action_items"]),
        by_property={k: PropertyBreakdown(**v) for k, v in data["by_property"].items()},
        by_source_pair={
            k: SourcePairBreakdown(**v) for k, v in data["by_source_pair"].items()
        },
        by_affected_type=data["by_affected_type"],
    )


# ─── Import Summary ─────────────────────────────────────────


@router.get(
    "/dashboard/import-summary",
    response_model=ImportSummaryResponse,
    status_code=200,
)
async def get_import_summary(
    project: uuid.UUID | None = Query(None, description="Project item ID"),
    batch_id: uuid.UUID | None = Query(None, description="Specific batch ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Most recent import results for the project.

    Returns summary counts and per-source breakdowns.
    """
    # Check project access if project provided
    if project:
        await require_project_access(db, project, current_user)

    data = await dashboard_service.get_import_summary(
        db, project_id=project, batch_id=batch_id
    )
    return ImportSummaryResponse(**data)


# ─── Temporal Trend ──────────────────────────────────────────


@router.get(
    "/dashboard/temporal-trend",
    response_model=TemporalTrendResponse,
    status_code=200,
)
async def get_temporal_trend(
    project: uuid.UUID | None = Query(None, description="Project item ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Action item counts at each milestone over time.

    Shows how changes, conflicts, and directives evolve
    across the project's milestone timeline.
    """
    # Check project access if project provided
    if project:
        await require_project_access(db, project, current_user)

    data = await dashboard_service.get_temporal_trend(db, project_id=project)

    return TemporalTrendResponse(
        milestones=[MilestoneTrend(**m) for m in data["milestones"]]
    )


# ─── Directive Status ───────────────────────────────────────


@router.get(
    "/dashboard/directive-status",
    response_model=DirectiveStatusResponse,
    status_code=200,
)
async def get_directive_status(
    project: uuid.UUID | None = Query(None, description="Project item ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Directive status grouped by target source.

    Shows pending vs fulfilled directive counts per source,
    plus global totals.
    """
    # Check project access if project provided
    if project:
        await require_project_access(db, project, current_user)

    data = await dashboard_service.get_directive_status(db, project_id=project)

    by_source = []
    for entry in data["by_source"]:
        source_id = entry["source_id"]
        # Handle case where source_id might be a string (non-UUID "unknown")
        if isinstance(source_id, str):
            try:
                source_id = uuid.UUID(source_id)
            except (ValueError, TypeError):
                continue  # Skip entries with non-UUID source IDs

        by_source.append(
            SourceDirectiveRollup(
                source_id=source_id,
                source_identifier=entry["source_identifier"],
                pending=entry["pending"],
                fulfilled=entry["fulfilled"],
            )
        )

    return DirectiveStatusResponse(
        total_pending=data["total_pending"],
        total_fulfilled=data["total_fulfilled"],
        by_source=by_source,
    )


# ─── Affected Items ─────────────────────────────────────


@router.get(
    "/dashboard/affected-items",
    response_model=AffectedItemsResponse,
    status_code=200,
)
async def get_affected_items(
    project: uuid.UUID | None = Query(None, description="Project item ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get affected items for the workflow perspective.

    Returns all spatial items that have workflow actions (changes, conflicts,
    directives), grouped by item_type, with per-item action counts.

    This is used by the center panel workflow perspective, which needs the
    full graph traversal (via _get_project_item_ids) rather than just
    immediate connected items.
    """
    # Check project access if project provided
    if project:
        await require_project_access(db, project, current_user)

    data = await dashboard_service.get_affected_items(db, project_id=project)

    groups = [
        AffectedItemGroup(
            item_type=g["item_type"],
            label=g["label"],
            count=g["count"],
            items=[
                {
                    "id": item["id"],
                    "identifier": item["identifier"],
                    "item_type": item["item_type"],
                    "action_counts": ItemActionCounts(
                        changes=item["action_counts"]["changes"],
                        conflicts=item["action_counts"]["conflicts"],
                        directives=item["action_counts"]["directives"],
                    ),
                }
                for item in g["items"]
            ],
        )
        for g in data["groups"]
    ]

    return AffectedItemsResponse(groups=groups)
