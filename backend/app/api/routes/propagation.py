"""
Propagation API routes — WP-18.2.

Endpoints:
  POST /spec/propagate           — Propagate confirmed extractions to graph
  GET  /spec/propagate/{batch_id}/assignments — List pending conditional assignments
  POST /spec/propagate/assign    — Assign concrete values to conditional properties
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.propagation import (
    AssignConditionalRequest,
    AssignConditionalResponse,
    PendingAssignment,
    PendingAssignmentsResponse,
    PropagateRequest,
    PropagateResponse,
    PropagationSummary,
)
from app.services.propagation_service import (
    assign_conditional_values,
    get_pending_assignments,
    propagate_extractions,
)


router = APIRouter(prefix="/spec/propagate", tags=["spec-propagation"])


@router.post("", response_model=PropagateResponse, status_code=201)
async def propagate(
    request: PropagateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Propagate confirmed extractions to section- and element-level snapshots.

    Prerequisites:
      - Extraction batch must exist and be in "confirmed" status.
      - The batch must have a milestone_id and extraction_results.

    Side effects:
      - Creates source-attributed snapshots (source_id = spec_section item)
      - Runs shared conflict detection on propagated values
      - Runs shared directive fulfillment check
      - Creates spec_section → element connections
      - Updates batch status to "propagated"
    """
    try:
        result = await propagate_extractions(db, request.batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    summary = PropagationSummary(
        batch_id=result.batch_id,
        status=result.status,
        section_snapshots_created=result.section_snapshots_created,
        element_snapshots_created=result.element_snapshots_created,
        element_snapshots_updated=result.element_snapshots_updated,
        conditionals_deferred=result.conditionals_deferred,
        conflicts_detected=result.conflicts_detected,
        conflicts_auto_resolved=result.conflicts_auto_resolved,
        directives_fulfilled=result.directives_fulfilled,
        discovered_entities=result.discovered_entities,
    )

    message = f"Propagated {result.element_snapshots_created} element snapshots"
    if result.conflicts_detected:
        message += f", {result.conflicts_detected} new conflicts"
    if result.conditionals_deferred:
        message += f", {result.conditionals_deferred} conditionals pending assignment"
    message += "."

    return PropagateResponse(summary=summary, message=message)


@router.get(
    "/{batch_id}/assignments",
    response_model=PendingAssignmentsResponse,
)
async def list_pending_assignments(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List elements with conditional properties needing user assignment.

    Returns each (element, property, conditional_assertions) tuple
    where the element's snapshot has _needs_assignment=True.
    """
    from uuid import UUID

    try:
        bid = UUID(batch_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid batch_id format")

    pending = await get_pending_assignments(db, bid)

    assignments = [
        PendingAssignment(
            element_id=p["element_id"],
            element_identifier=p["element_identifier"],
            property_name=p["property_name"],
            assertions=p["assertions"],
            section_number=p["section_number"],
            section_item_id=p["section_item_id"],
        )
        for p in pending
    ]

    return PendingAssignmentsResponse(
        batch_id=bid,
        assignments=assignments,
        total=len(assignments),
    )


@router.post("/assign", response_model=AssignConditionalResponse)
async def assign_conditionals(
    request: AssignConditionalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Assign concrete values to conditional properties.

    For each assignment:
      - Replaces the conditional structure with a concrete value
      - Runs conflict detection on the now-concrete value
      - Removes _needs_assignment flag
    """
    assignment_dicts = [
        {
            "element_ids": [str(eid) for eid in a.element_ids],
            "property_name": a.property_name,
            "value": a.value,
            "source_condition": a.source_condition,
            "section_item_id": str(a.section_item_id),
        }
        for a in request.assignments
    ]

    try:
        result = await assign_conditional_values(
            db, assignment_dicts, request.batch_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return AssignConditionalResponse(
        assignments_made=result["assignments_made"],
        conflicts_detected=result["conflicts_detected"],
    )
