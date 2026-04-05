"""
Snapshots API routes — WP-5: Full CRUD with effective values and resolved view.

The snapshot triple (item_id, context_id, source_id) answers:
  WHAT is being described, WHEN, and WHO SAYS.

Key operations:
  - Upsert: same triple updates existing snapshot rather than creating duplicate
  - Effective value: most recent snapshot from a source, ordered by milestone ordinal
  - Resolved view: per-property status across all sources at a context
"""

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_access, get_project_for_item
from app.core.database import get_db
from app.core.type_config import get_conflict_excluded_types, get_type_config
from app.models.core import Connection, Item, Snapshot
from app.models.infrastructure import User
from app.schemas.items import ItemSummary
from app.schemas.snapshots import (
    EffectiveValue,
    PropertyResolution,
    PropertyWorkflowRefs,
    ResolvedView,
    SnapshotCreate,
    SnapshotResponse,
)
from app.services.normalization import values_match

router = APIRouter()


# ─── Helpers ───────────────────────────────────────────────────


async def _get_item_or_404(
    db: AsyncSession, item_id: uuid.UUID, label: str = "Item"
) -> Item:
    """Fetch an item or raise 404."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail=f"{label} not found: {item_id}")
    return item


async def _validate_context(db: AsyncSession, context_id: uuid.UUID) -> Item:
    """Validate that context_id refers to a milestone (is_context_type)."""
    context = await _get_item_or_404(db, context_id, "Context (milestone)")
    type_cfg = get_type_config(context.item_type)
    if not type_cfg or not type_cfg.is_context_type:
        raise HTTPException(
            status_code=400,
            detail=f"Context must be a milestone item. Got type '{context.item_type}' "
            f"which is not a context type.",
        )
    return context


def _get_ordinal(item: Item) -> int:
    """Extract milestone ordinal from item properties, defaulting to 0."""
    return item.properties.get("ordinal", 0) if item.properties else 0


# ─── CRUD ──────────────────────────────────────────────────────


@router.post("/", response_model=SnapshotResponse, status_code=201)
async def create_snapshot(
    payload: SnapshotCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create or upsert a source-attributed snapshot.

    If a snapshot already exists for the same triple (item_id, context_id,
    source_id), its properties are replaced (upsert semantics).

    Validates:
    - All referenced items exist
    - context_id is a milestone (is_context_type)
    """
    # Validate item and source exist
    await _get_item_or_404(db, payload.item_id, "Item")
    await _get_item_or_404(db, payload.source_id, "Source")

    # Validate context is a milestone
    await _validate_context(db, payload.context_id)

    # Check project access via item
    project_id = await get_project_for_item(db, payload.item_id)
    if project_id:
        await require_project_access(db, project_id, current_user)

    # Check for existing snapshot with same triple (upsert)
    existing_result = await db.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == payload.item_id,
                Snapshot.context_id == payload.context_id,
                Snapshot.source_id == payload.source_id,
            )
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Upsert: update properties on existing snapshot
        existing.properties = payload.properties
        await db.flush()
        await db.refresh(existing)
        return existing

    # Create new snapshot
    snapshot = Snapshot(
        item_id=payload.item_id,
        context_id=payload.context_id,
        source_id=payload.source_id,
        properties=payload.properties,
        created_by=current_user.id,
    )
    db.add(snapshot)
    await db.flush()
    await db.refresh(snapshot)
    return snapshot


@router.get("/", response_model=list[SnapshotResponse])
async def list_snapshots(
    item_id: uuid.UUID | None = Query(None, description="Filter by item (WHAT)"),
    context_id: uuid.UUID | None = Query(
        None, description="Filter by context/milestone (WHEN)"
    ),
    source_id: uuid.UUID | None = Query(
        None, description="Filter by source (WHO SAYS)"
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List snapshots with optional triple filters."""
    query = select(Snapshot).order_by(Snapshot.created_at.desc())

    if item_id:
        query = query.where(Snapshot.item_id == item_id)
    if context_id:
        query = query.where(Snapshot.context_id == context_id)
    if source_id:
        query = query.where(Snapshot.source_id == source_id)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(
    snapshot_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single snapshot."""
    result = await db.execute(select(Snapshot).where(Snapshot.id == snapshot_id))
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.delete("/{snapshot_id}", status_code=204)
async def delete_snapshot(
    snapshot_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a snapshot."""
    result = await db.execute(select(Snapshot).where(Snapshot.id == snapshot_id))
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    await db.delete(snapshot)


# ─── Effective Value ───────────────────────────────────────────


@router.get("/item/{item_id}/effective", response_model=EffectiveValue)
async def get_effective_value(
    item_id: uuid.UUID,
    source: uuid.UUID = Query(..., description="Source to get effective value from"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a source's effective value for an item.

    The effective value is the most recent snapshot from this source,
    ordered by milestone ordinal (not created_at). A value is current
    until superseded — if no snapshot exists at CD, the DD value
    remains effective.

    Per Decision 3: ordering uses milestone ordinal via JOIN to the
    context item's properties.
    """
    await _get_item_or_404(db, item_id, "Item")
    source_item = await _get_item_or_404(db, source, "Source")

    # Check project access via item
    project_id = await get_project_for_item(db, item_id)
    if project_id:
        await require_project_access(db, project_id, current_user)

    # Get all snapshots from this source for this item
    snapshots_result = await db.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == item_id,
                Snapshot.source_id == source,
            )
        )
    )
    snapshots = snapshots_result.scalars().all()

    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=f"No snapshots found for item {item_id} from source {source}",
        )

    # Load context items to get ordinals
    context_ids = {s.context_id for s in snapshots}
    contexts_result = await db.execute(select(Item).where(Item.id.in_(context_ids)))
    contexts = {c.id: c for c in contexts_result.scalars().all()}

    # Sort by milestone ordinal (highest = most recent), not created_at
    snapshots_with_ordinal = [
        (s, _get_ordinal(contexts.get(s.context_id, Item(properties={}))))
        for s in snapshots
    ]
    snapshots_with_ordinal.sort(key=lambda x: x[1], reverse=True)

    best_snapshot, _ = snapshots_with_ordinal[0]
    best_context = contexts.get(best_snapshot.context_id)

    return EffectiveValue(
        properties=best_snapshot.properties,
        as_of_context=ItemSummary(
            id=best_context.id,
            item_type=best_context.item_type,
            identifier=best_context.identifier,
        ),
        source=ItemSummary(
            id=source_item.id,
            item_type=source_item.item_type,
            identifier=source_item.identifier,
        ),
        snapshot_created_at=best_snapshot.created_at,
    )


# ─── Resolved View ────────────────────────────────────────────


@router.get("/item/{item_id}/resolved")  # response_model temporarily removed for debug
async def get_resolved_view(
    item_id: uuid.UUID,
    context: uuid.UUID | None = Query(
        None, description="Milestone context to resolve at"
    ),
    mode: str = Query(
        "cumulative",
        description="Value mode: cumulative, submitted, or current",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the resolved view for an item at a specific context.

    Uses effective values: for each source, finds the most recent
    snapshot at or before the given context (by milestone ordinal).
    Then compares across sources per property.

    Property statuses:
    - 'agreed': multiple sources, all values match
    - 'single_source': only one source has spoken
    - 'conflicted': sources disagree
    - 'resolved': was conflicted, now has a decision snapshot
    """
    # Validate mode
    if mode not in ("cumulative", "submitted", "current"):
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

    # context is required for cumulative and submitted modes, not needed for current
    if mode != "current" and context is None:
        raise HTTPException(
            status_code=400,
            detail="context parameter is required for cumulative and submitted modes.",
        )

    item = await _get_item_or_404(db, item_id, "Item")

    # Check project access via item
    project_id = await get_project_for_item(db, item_id)
    if project_id:
        await require_project_access(db, project_id, current_user)
    context_item = None
    context_ordinal = 0
    if mode != "current":
        # For cumulative and submitted, validate and get ordinal from context
        context_item = await _validate_context(db, context)
        context_ordinal = _get_ordinal(context_item)

    # Get ALL snapshots for this item from document sources
    # (exclude workflow item self-snapshots)
    all_snapshots_result = await db.execute(
        select(Snapshot).where(Snapshot.item_id == item_id)
    )
    all_snapshots = all_snapshots_result.scalars().all()

    if not all_snapshots:
        context_summary = None
        if context_item:
            context_summary = ItemSummary(
                id=context_item.id,
                item_type=context_item.item_type,
                identifier=context_item.identifier,
            )
        return ResolvedView(
            item=ItemSummary(
                id=item.id, item_type=item.item_type, identifier=item.identifier
            ),
            context=context_summary,
            mode=mode,
            properties=[],
            source_count=0,
            snapshot_count=0,
        )

    # Load all contexts to get ordinals
    context_ids = {s.context_id for s in all_snapshots}
    contexts_result = await db.execute(select(Item).where(Item.id.in_(context_ids)))
    contexts = {c.id: c for c in contexts_result.scalars().all()}

    # Load all sources for display names
    source_ids = {s.source_id for s in all_snapshots}
    sources_result = await db.execute(select(Item).where(Item.id.in_(source_ids)))
    sources = {s.id: s for s in sources_result.scalars().all()}

    # Filter to document sources (exclude types marked exclude_from_conflicts)
    excluded_types = get_conflict_excluded_types()
    document_snapshots = [
        s
        for s in all_snapshots
        if s.source_id in sources
        and sources[s.source_id].item_type not in excluded_types
    ]

    # Determine effective snapshots per source based on mode
    effective_by_source: dict[uuid.UUID, Snapshot] = {}
    source_origin_context: dict[uuid.UUID, Item] = {}

    if mode == "submitted":
        # Submitted mode: strict context match, no carry-forward
        for s in document_snapshots:
            if s.context_id == context:
                effective_by_source[s.source_id] = s
        # For submitted mode, source_origin_context stays empty (always None for effective_context)

    elif mode == "current":
        # Current mode: latest snapshot per source across ALL milestones, no ordinal ceiling
        current_by_source_dict: dict[uuid.UUID, Snapshot] = {}
        for s in document_snapshots:
            ctx = contexts.get(s.context_id)
            if not ctx:
                continue
            snap_ordinal = _get_ordinal(ctx)

            existing = current_by_source_dict.get(s.source_id)
            if existing is None:
                current_by_source_dict[s.source_id] = s
            else:
                existing_ctx = contexts.get(existing.context_id)
                existing_ordinal = _get_ordinal(existing_ctx) if existing_ctx else 0
                if snap_ordinal > existing_ordinal:
                    current_by_source_dict[s.source_id] = s

        effective_by_source = current_by_source_dict
        # For current mode, always populate source_origin_context
        for src_id, snap in effective_by_source.items():
            source_origin_context[src_id] = contexts.get(snap.context_id)
        # Set context_item and context_ordinal for current mode
        context_item = None
        context_ordinal = float("inf")

    else:  # mode == "cumulative"
        # Cumulative mode: find effective snapshot per source with ordinal <= context ordinal
        for s in document_snapshots:
            ctx = contexts.get(s.context_id)
            if not ctx:
                continue
            snap_ordinal = _get_ordinal(ctx)
            if snap_ordinal > context_ordinal:
                continue  # Future snapshot, skip
            if context_ordinal > 0 and snap_ordinal == 0:
                continue  # Unset ordinal excluded at non-zero context

            existing = effective_by_source.get(s.source_id)
            if existing is None:
                effective_by_source[s.source_id] = s
            else:
                existing_ctx = contexts.get(existing.context_id)
                existing_ordinal = _get_ordinal(existing_ctx) if existing_ctx else 0
                if snap_ordinal > existing_ordinal:
                    effective_by_source[s.source_id] = s

        # Create a mapping of which context each source's effective snapshot came from
        for src_id, snap in effective_by_source.items():
            source_origin_context[src_id] = contexts.get(snap.context_id)

    # Check for decision snapshots (resolved conflicts)
    decision_snapshots = [
        s
        for s in all_snapshots
        if s.source_id in sources and sources[s.source_id].item_type == "decision"
    ]
    resolved_properties: set[str] = set()
    resolved_values: dict[str, object] = {}
    for ds in decision_snapshots:
        ds_ctx = contexts.get(ds.context_id)
        if ds_ctx and _get_ordinal(ds_ctx) <= context_ordinal:
            rp = ds.properties.get("property_name") or ds.properties.get(
                "property_path"
            )
            if rp:
                resolved_properties.add(rp)
                rv = ds.properties.get("resolved_value")
                if rv is not None:
                    resolved_values[rp] = rv

    # ── Workflow item discovery ──────────────────────────────────
    # Find all workflow items (conflict, change, directive, decision)
    # connected to this item. We need their IDs and the property
    # they reference (stored in the workflow item's own properties).
    workflow_types = {"conflict", "change", "directive", "decision"}

    # Find workflow item IDs connected to this item (both directions).
    # Using subqueries on connections then loading items avoids JOIN
    # ambiguity issues across databases.
    workflow_ids_as_source = await db.execute(
        select(Connection.source_item_id).where(Connection.target_item_id == item_id)
    )
    workflow_ids_as_target = await db.execute(
        select(Connection.target_item_id).where(Connection.source_item_id == item_id)
    )
    candidate_ids = {row[0] for row in workflow_ids_as_source.all()} | {
        row[0] for row in workflow_ids_as_target.all()
    }
    candidate_ids.discard(item_id)  # Don't include self

    if candidate_ids:
        workflow_items_result = await db.execute(
            select(Item).where(
                and_(
                    Item.id.in_(candidate_ids),
                    Item.item_type.in_(workflow_types),
                )
            )
        )
        all_workflow_items = list(workflow_items_result.scalars().all())
    else:
        all_workflow_items = []

    # Deduplicate
    seen_workflow: set[uuid.UUID] = set()
    unique_workflow: list[Item] = []
    for wi in all_workflow_items:
        if wi.id not in seen_workflow:
            seen_workflow.add(wi.id)
            unique_workflow.append(wi)

    # Index workflow items by property name
    workflow_by_property: dict[str, dict[str, list[Item]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for wi in unique_workflow:
        prop_name = wi.properties.get("property_name") or wi.properties.get(
            "property_path"
        )
        if prop_name:
            workflow_by_property[prop_name][wi.item_type].append(wi)
        elif wi.item_type == "change" and wi.properties.get("changes"):
            # "Added" or multi-property change: index under each changed property
            for changed_prop in wi.properties["changes"]:
                workflow_by_property[changed_prop][wi.item_type].append(wi)

    # Collect all properties across all effective snapshots.
    # Exclude internal _raw suffix properties (WP-6b dual storage).
    all_props: set[str] = set()
    for snap in effective_by_source.values():
        all_props.update(k for k in snap.properties.keys() if not k.endswith("_raw"))

    # Build per-property resolution
    property_resolutions = []
    for prop_name in sorted(all_props):
        source_values: dict[str, object] = {}
        source_id_map: dict[str, str] = {}
        contributing_sources: list[uuid.UUID] = []
        for src_id, snap in effective_by_source.items():
            val = snap.properties.get(prop_name)
            if val is not None:
                src = sources.get(src_id)
                src_label = src.identifier if src else str(src_id)
                source_values[src_label] = val
                source_id_map[src_label] = str(src_id)
                contributing_sources.append(src_id)

        if len(source_values) == 0:
            continue

        # Determine status
        unique_vals = list(source_values.values())

        # Check resolution: decision snapshots on the item OR connected
        # conflict item with status="resolved" (conflict resolution snapshots
        # live on the conflict item, not the affected item — per Decision 8).
        prop_conflicts = workflow_by_property.get(prop_name, {}).get("conflict", [])
        conflict_resolved = any(
            (c.properties or {}).get("status") == "resolved" for c in prop_conflicts
        )
        if prop_name in resolved_properties or conflict_resolved:
            status = "resolved"
            # Try decision snapshot value first, then decision item's resolved_value
            rv = resolved_values.get(prop_name)
            if rv is None and conflict_resolved:
                prop_decisions = workflow_by_property.get(prop_name, {}).get(
                    "decision", []
                )
                for d in prop_decisions:
                    rv = (d.properties or {}).get("resolved_value")
                    if rv is not None:
                        break
            value = rv if rv is not None else unique_vals[0]
        elif len(source_values) == 1:
            status = "single_source"
            value = unique_vals[0]
        else:
            # Check if all values agree (with normalization)
            first = unique_vals[0]
            all_agree = all(
                values_match(str(first), str(v), property_name=prop_name)
                for v in unique_vals[1:]
            )
            if all_agree:
                status = "agreed"
                value = first
            else:
                status = "conflicted"
                value = None

        # Compute effective_context based on mode
        eff_ctx = None
        if mode == "submitted":
            # Submitted mode: always None (values are by definition at the requested context)
            eff_ctx = None
        elif mode == "current":
            # Current mode: always populate effective_context with the origin milestone
            origin_context_ids = set()
            for src_id in contributing_sources:
                origin_ctx = source_origin_context.get(src_id)
                if origin_ctx:
                    origin_context_ids.add(origin_ctx.identifier)
            if origin_context_ids:
                # Use the highest (latest) origin context
                eff_ctx = sorted(origin_context_ids)[-1]
        elif mode == "cumulative":
            # Cumulative mode: populate only if value was carried forward
            if context_item:
                all_submitted_at_context = True
                origin_context_item = None
                for src_id in contributing_sources:
                    origin_ctx = source_origin_context.get(src_id)
                    if origin_ctx and origin_ctx.id != context_item.id:
                        all_submitted_at_context = False
                        # Use the first (earliest) origin context found
                        if origin_context_item is None:
                            origin_context_item = origin_ctx

                # If not all sources submitted at the requested context, set effective_context
                if not all_submitted_at_context and origin_context_item:
                    eff_ctx = origin_context_item.identifier

        # ── Build workflow refs for this property ──
        prop_workflow = workflow_by_property.get(prop_name, {})
        workflow_refs = None

        if prop_workflow:
            conflicts = prop_workflow.get("conflict", [])
            # Exclude acknowledged changes — they're no longer active workflow items
            changes = [
                c
                for c in prop_workflow.get("change", [])
                if (c.properties or {}).get("status", "").lower() != "acknowledged"
            ]
            decisions = prop_workflow.get("decision", [])
            # Exclude fulfilled directives
            directives = [
                d
                for d in prop_workflow.get("directive", [])
                if (d.properties or {}).get("status", "").lower() != "fulfilled"
            ]

            # For resolution metadata, use the decision item's properties.
            res_metadata = None
            if decisions:
                d = decisions[0]
                d_props = d.properties or {}
                res_metadata = {
                    "decided_by": d_props.get("decided_by"),
                    "resolved_at": d_props.get("resolved_at"),
                    "method": d_props.get("method"),
                    "rationale": d_props.get("rationale"),
                    "chosen_source": d_props.get("chosen_source"),
                }

            workflow_refs = PropertyWorkflowRefs(
                conflict_id=conflicts[0].id if conflicts else None,
                change_ids=[c.id for c in changes],
                decision_id=decisions[0].id if decisions else None,
                directive_ids=[d.id for d in directives],
                resolution_metadata=res_metadata,
            )

        property_resolutions.append(
            PropertyResolution(
                property_name=prop_name,
                status=status,
                value=value,
                sources=source_values,
                source_ids=source_id_map,
                effective_context=eff_ctx,
                workflow=workflow_refs,
            )
        )

    # Build context summary if we have one
    context_summary = None
    if context_item:
        context_summary = ItemSummary(
            id=context_item.id,
            item_type=context_item.item_type,
            identifier=context_item.identifier,
        )

    resolved_view = ResolvedView(
        item=ItemSummary(
            id=item.id, item_type=item.item_type, identifier=item.identifier
        ),
        context=context_summary,
        mode=mode,
        properties=property_resolutions,
        source_count=len(effective_by_source),
        snapshot_count=len(document_snapshots),
    )
    # Temporary debug: include workflow discovery stats
    result_dict = resolved_view.model_dump()
    result_dict["_debug_workflow"] = {
        "candidate_ids_count": len(candidate_ids),
        "workflow_items_count": len(all_workflow_items),
        "workflow_types_found": [wi.item_type for wi in all_workflow_items],
        "indexed_properties": list(workflow_by_property.keys()),
    }
    return result_dict
