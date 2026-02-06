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

from app.core.database import get_db
from app.core.type_config import get_type_config
from app.models.core import Item, Snapshot
from app.schemas.items import ItemSummary
from app.schemas.snapshots import (
    EffectiveValue,
    PropertyResolution,
    ResolvedView,
    SnapshotCreate,
    SnapshotResponse,
)
from app.services.normalization import values_match

router = APIRouter()


# ─── Helpers ───────────────────────────────────────────────────

async def _get_item_or_404(db: AsyncSession, item_id: uuid.UUID, label: str = "Item") -> Item:
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
    )
    db.add(snapshot)
    await db.flush()
    await db.refresh(snapshot)
    return snapshot


@router.get("/", response_model=list[SnapshotResponse])
async def list_snapshots(
    item_id: uuid.UUID | None = Query(None, description="Filter by item (WHAT)"),
    context_id: uuid.UUID | None = Query(None, description="Filter by context/milestone (WHEN)"),
    source_id: uuid.UUID | None = Query(None, description="Filter by source (WHO SAYS)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
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
    item = await _get_item_or_404(db, item_id, "Item")
    source_item = await _get_item_or_404(db, source, "Source")

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
    contexts_result = await db.execute(
        select(Item).where(Item.id.in_(context_ids))
    )
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

@router.get("/item/{item_id}/resolved", response_model=ResolvedView)
async def get_resolved_view(
    item_id: uuid.UUID,
    context: uuid.UUID = Query(..., description="Milestone context to resolve at"),
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
    item = await _get_item_or_404(db, item_id, "Item")
    context_item = await _validate_context(db, context)
    context_ordinal = _get_ordinal(context_item)

    # Get ALL snapshots for this item from document sources
    # (exclude workflow item self-snapshots)
    all_snapshots_result = await db.execute(
        select(Snapshot).where(Snapshot.item_id == item_id)
    )
    all_snapshots = all_snapshots_result.scalars().all()

    if not all_snapshots:
        return ResolvedView(
            item=ItemSummary(id=item.id, item_type=item.item_type, identifier=item.identifier),
            context=ItemSummary(id=context_item.id, item_type=context_item.item_type, identifier=context_item.identifier),
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

    # Filter to document sources (exclude workflow self-snapshots)
    workflow_types = {"change", "conflict", "decision", "note"}
    document_snapshots = [
        s for s in all_snapshots
        if s.source_id in sources
        and sources[s.source_id].item_type not in workflow_types
    ]

    # Find effective snapshot per source: most recent by ordinal <= context ordinal
    effective_by_source: dict[uuid.UUID, Snapshot] = {}
    for s in document_snapshots:
        ctx = contexts.get(s.context_id)
        if not ctx:
            continue
        snap_ordinal = _get_ordinal(ctx)
        if snap_ordinal > context_ordinal:
            continue  # Future snapshot, skip

        existing = effective_by_source.get(s.source_id)
        if existing is None:
            effective_by_source[s.source_id] = s
        else:
            existing_ctx = contexts.get(existing.context_id)
            existing_ordinal = _get_ordinal(existing_ctx) if existing_ctx else 0
            if snap_ordinal > existing_ordinal:
                effective_by_source[s.source_id] = s

    # Check for decision snapshots (resolved conflicts)
    decision_snapshots = [
        s for s in all_snapshots
        if s.source_id in sources
        and sources[s.source_id].item_type == "decision"
    ]
    resolved_properties: set[str] = set()
    resolved_values: dict[str, object] = {}
    for ds in decision_snapshots:
        ds_ctx = contexts.get(ds.context_id)
        if ds_ctx and _get_ordinal(ds_ctx) <= context_ordinal:
            rp = ds.properties.get("property_name") or ds.properties.get("property_path")
            if rp:
                resolved_properties.add(rp)
                rv = ds.properties.get("resolved_value")
                if rv is not None:
                    resolved_values[rp] = rv

    # Collect all properties across all effective snapshots
    all_props: set[str] = set()
    for snap in effective_by_source.values():
        all_props.update(snap.properties.keys())

    # Build per-property resolution
    property_resolutions = []
    for prop_name in sorted(all_props):
        source_values: dict[str, object] = {}
        for src_id, snap in effective_by_source.items():
            val = snap.properties.get(prop_name)
            if val is not None:
                src = sources.get(src_id)
                src_label = src.identifier if src else str(src_id)
                source_values[src_label] = val

        if len(source_values) == 0:
            continue

        # Determine status
        unique_vals = list(source_values.values())

        if prop_name in resolved_properties:
            status = "resolved"
            value = resolved_values.get(prop_name, unique_vals[0])
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

        property_resolutions.append(PropertyResolution(
            property_name=prop_name,
            status=status,
            value=value,
            sources=source_values,
        ))

    return ResolvedView(
        item=ItemSummary(id=item.id, item_type=item.item_type, identifier=item.identifier),
        context=ItemSummary(id=context_item.id, item_type=context_item.item_type, identifier=context_item.identifier),
        properties=property_resolutions,
        source_count=len(effective_by_source),
        snapshot_count=len(document_snapshots),
    )
