"""
Workflow routes — WP-12a.

Conflict resolution, change acknowledgment, directive management,
and action-item queries.

Endpoints:
  POST /items/{conflict_id}/resolve      — resolve a conflict
  POST /items/{change_id}/acknowledge    — acknowledge a change
  POST /items/{directive_id}/fulfill     — manually fulfill a directive
  POST /action-items/bulk-resolve        — batch resolve conflicts
  GET  /action-items                     — pending action item rollup
  GET  /directives                       — list directives with filters
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.core import Item
from app.schemas.items import ItemResponse
from app.schemas.resolution import (
    ActionItemRollup,
    BulkResolveEntry,
    BulkResolveRequest,
    BulkResolveResponse,
    BulkResolveResult,
    ChangeAcknowledgeResponse,
    ConflictResolveRequest,
    ConflictResolveResponse,
    DirectiveDetail,
    DirectiveFulfillResponse,
    DirectiveListResponse,
    StatusTransitionResponse,
)
from app.services import resolution_service

router = APIRouter(tags=["workflow"])


# ─── Conflict Resolution ─────────────────────────────────────


@router.post(
    "/items/{conflict_id}/resolve",
    response_model=ConflictResolveResponse,
    status_code=200,
)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    payload: ConflictResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve a conflict by creating a decision and directives.

    Creates:
    - Decision item with self-sourced snapshot
    - Resolution snapshot on conflict (source_id = decision_id, per Decision 8)
    - Directive items for non-chosen sources that need to update
    """
    # Load and validate conflict
    result = await db.execute(
        select(Item).where(and_(Item.id == conflict_id, Item.item_type == "conflict"))
    )
    conflict = result.scalar_one_or_none()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")

    try:
        decision_item, directives = await resolution_service.resolve_conflict(
            db=db,
            conflict_item=conflict,
            chosen_value=payload.chosen_value,
            chosen_source_id=payload.chosen_source_id,
            method=payload.method.value,
            rationale=payload.rationale,
            decided_by=payload.decided_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    directives_fulfilled = sum(
        1 for d in directives if d.properties.get("status") == "fulfilled"
    )

    return ConflictResolveResponse(
        decision_item=ItemResponse.model_validate(decision_item),
        conflict_item_id=conflict_id,
        conflict_updated=True,
        directives_created=len(directives),
        directives_fulfilled=directives_fulfilled,
    )


# ─── Change Acknowledgment ───────────────────────────────────


@router.post(
    "/items/{change_id}/acknowledge",
    response_model=ChangeAcknowledgeResponse,
    status_code=200,
)
async def acknowledge_change(
    change_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge a detected change."""
    result = await db.execute(
        select(Item).where(and_(Item.id == change_id, Item.item_type == "change"))
    )
    change = result.scalar_one_or_none()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    try:
        await resolution_service.acknowledge_change(db, change)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ChangeAcknowledgeResponse(change_item_id=change_id)


# ─── Directive Fulfillment ───────────────────────────────────


@router.post(
    "/items/{directive_id}/fulfill",
    response_model=DirectiveFulfillResponse,
    status_code=200,
)
async def fulfill_directive(
    directive_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Manually fulfill a directive (for Phase A testing)."""
    result = await db.execute(
        select(Item).where(and_(Item.id == directive_id, Item.item_type == "directive"))
    )
    directive = result.scalar_one_or_none()
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")

    try:
        await resolution_service.fulfill_directive(db, directive)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return DirectiveFulfillResponse(directive_item_id=directive_id)


# ─── Bulk Resolution ─────────────────────────────────────────


@router.post(
    "/action-items/bulk-resolve",
    response_model=BulkResolveResponse,
    status_code=200,
)
async def bulk_resolve(
    payload: BulkResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Batch resolve multiple conflicts.

    Reports partial success: each resolution is attempted independently.
    Failures do not roll back successful resolutions.
    """
    results: list[BulkResolveResult] = []

    for entry in payload.resolutions:
        try:
            # Load conflict
            result = await db.execute(
                select(Item).where(
                    and_(
                        Item.id == entry.conflict_item_id,
                        Item.item_type == "conflict",
                    )
                )
            )
            conflict = result.scalar_one_or_none()
            if not conflict:
                results.append(
                    BulkResolveResult(
                        conflict_item_id=entry.conflict_item_id,
                        success=False,
                        error="Conflict not found",
                    )
                )
                continue

            decision_item, directives = await resolution_service.resolve_conflict(
                db=db,
                conflict_item=conflict,
                chosen_value=entry.chosen_value,
                chosen_source_id=entry.chosen_source_id,
                method=entry.method.value,
                rationale=entry.rationale,
                decided_by=entry.decided_by,
            )

            results.append(
                BulkResolveResult(
                    conflict_item_id=entry.conflict_item_id,
                    success=True,
                    decision_item_id=decision_item.id,
                    directives_created=len(directives),
                )
            )
        except Exception as e:
            results.append(
                BulkResolveResult(
                    conflict_item_id=entry.conflict_item_id,
                    success=False,
                    error=str(e),
                )
            )

    succeeded = sum(1 for r in results if r.success)
    return BulkResolveResponse(
        total_attempted=len(payload.resolutions),
        total_succeeded=succeeded,
        total_failed=len(payload.resolutions) - succeeded,
        results=results,
    )


# ─── Status Transitions (Decision 13) ────────────────────────


async def _load_workflow_item(
    db: AsyncSession,
    item_id: uuid.UUID,
) -> Item:
    """Load a workflow item or raise 404."""
    result = await db.execute(
        select(Item).where(
            and_(
                Item.id == item_id,
                Item.item_type.in_(("change", "conflict", "directive")),
            )
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow item not found: {item_id}",
        )
    return item


@router.post(
    "/items/{item_id}/start-review",
    response_model=StatusTransitionResponse,
    status_code=200,
)
async def start_review(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Transition a workflow item from detected → in_review.

    DS-2 §6.3: Signals to the team that someone is actively examining
    this item. Appears on Surface 2 (workflow item view) only.
    """
    item = await _load_workflow_item(db, item_id)
    try:
        previous = await resolution_service.start_review(db, item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StatusTransitionResponse(
        item_id=item_id,
        item_type=item.item_type,
        previous_status=previous,
        new_status="in_review",
    )


@router.post(
    "/items/{item_id}/hold",
    response_model=StatusTransitionResponse,
    status_code=200,
)
async def hold_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Place a workflow item on hold.

    DS-2 §6.5: Hold from any active state. Stores pre-hold status
    so resume can restore it. Pip shifts to filed color.
    """
    item = await _load_workflow_item(db, item_id)
    try:
        previous = await resolution_service.hold_item(db, item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StatusTransitionResponse(
        item_id=item_id,
        item_type=item.item_type,
        previous_status=previous,
        new_status="hold",
    )


@router.post(
    "/items/{item_id}/resume-review",
    response_model=StatusTransitionResponse,
    status_code=200,
)
async def resume_review(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Resume a held workflow item.

    DS-2 §6.5: Restores the pre-hold status (detected or in_review).
    """
    item = await _load_workflow_item(db, item_id)
    try:
        previous = await resolution_service.resume_review(db, item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # The actual new status is the restored pre-hold status.
    new_status = item.properties.get("status", "detected")

    return StatusTransitionResponse(
        item_id=item_id,
        item_type=item.item_type,
        previous_status=previous,
        new_status=new_status,
    )


# ─── Action Items ────────────────────────────────────────────


@router.get(
    "/action-items",
    response_model=ActionItemRollup,
    status_code=200,
)
async def get_action_items(
    project_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary of pending action items.

    Returns rollup counts for changes, conflicts, and directives,
    broken down by type and by property.
    """
    rollup = await resolution_service.get_action_items_rollup(db, project_id)
    return ActionItemRollup(**rollup)


# ─── Directives ──────────────────────────────────────────────


@router.get(
    "/directives",
    response_model=DirectiveListResponse,
    status_code=200,
)
async def get_directives(
    source_id: uuid.UUID | None = Query(None, description="Filter by target source"),
    property_name: str | None = Query(None, description="Filter by property name"),
    status: str | None = Query(
        None, description="Filter by status: pending, fulfilled, superseded"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    List directives with optional filtering.

    Commonly used to find pending directives for a specific source:
    GET /directives?source_id=<spec_uuid>&status=pending
    """
    directives, pending_by_source = await resolution_service.list_directives(
        db,
        source_id=source_id,
        property_name=property_name,
        status=status,
    )

    directive_details = [
        DirectiveDetail(
            id=d.id,
            identifier=d.identifier,
            property_name=d.properties.get("property_name", ""),
            target_value=d.properties.get("target_value"),
            target_source_id=(
                uuid.UUID(d.properties["target_source_id"])
                if d.properties.get("target_source_id")
                else None
            ),
            affected_item_id=(
                uuid.UUID(d.properties["affected_item_id"])
                if d.properties.get("affected_item_id")
                else None
            ),
            decision_item_id=(
                uuid.UUID(d.properties["decision_item_id"])
                if d.properties.get("decision_item_id")
                else None
            ),
            status=d.properties.get("status", "unknown"),
            created_at=d.created_at.isoformat() if d.created_at else None,
        )
        for d in directives
    ]

    return DirectiveListResponse(
        directives=directive_details,
        total=len(directive_details),
        pending_by_source=pending_by_source,
    )
