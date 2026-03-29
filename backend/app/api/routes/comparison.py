"""
Temporal comparison API routes — WP-8.

Compares item snapshots across milestones to detect additions, removals,
modifications, and unchanged items. Supports both source-filtered and
multi-source effective value approaches.

The comparison uses milestone ordinals (from item properties) to determine
which snapshots are effective at each context.
"""

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_access, get_project_for_item
from app.core.database import get_db
from app.core.type_config import get_type_config
from app.models.core import Connection, Item, Snapshot
from app.models.infrastructure import User
from app.schemas.comparison import (
    ComparisonRequest,
    ComparisonResult,
    ComparisonSummary,
    ItemComparison,
    PropertyChange,
)
from app.schemas.items import ItemSummary
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


async def _get_children_of_parent(
    db: AsyncSession, parent_id: uuid.UUID
) -> list[uuid.UUID]:
    """
    Get all items connected to parent as target (i.e., all children).

    Convention: parent → child means container/authority.
    We look for connections where parent is the source.
    """
    result = await db.execute(
        select(Connection.target_item_id).where(Connection.source_item_id == parent_id)
    )
    return result.scalars().all()


async def _get_snapshot_at_context_submitted(
    db: AsyncSession,
    item_id: uuid.UUID,
    context_id: uuid.UUID,
    source_id: uuid.UUID | None = None,
) -> Snapshot | None:
    """
    Get the snapshot for an item at exactly the given context (submitted mode).

    Uses strict context_id matching. No carry-forward.
    If source_id is provided, filter to that source only.
    """
    # Query snapshots for this item at exactly the given context
    query = select(Snapshot).where(
        (Snapshot.item_id == item_id) & (Snapshot.context_id == context_id)
    )
    if source_id:
        query = query.where(Snapshot.source_id == source_id)

    result = await db.execute(query)
    snapshots = result.scalars().all()

    if not snapshots:
        return None

    # If multiple snapshots at this context from the same source, pick one (shouldn't happen)
    return snapshots[0]


async def _get_effective_snapshot_at_context(
    db: AsyncSession,
    item_id: uuid.UUID,
    context_id: uuid.UUID,
    source_id: uuid.UUID | None = None,
    contexts_cache: dict[uuid.UUID, Item] | None = None,
) -> Snapshot | None:
    """
    Get the effective snapshot for an item at a specific context.

    The effective snapshot is the most recent by milestone ordinal
    (as of the given context). If the context is before all snapshots
    exist, return None.

    If source_id is provided, filter to that source only.
    Otherwise, return the most recent snapshot from any source.
    """
    if contexts_cache is None:
        contexts_cache = {}

    # Get or fetch the target context
    if context_id not in contexts_cache:
        ctx_item = await _get_item_or_404(db, context_id, "Context")
        contexts_cache[context_id] = ctx_item
    target_context = contexts_cache[context_id]
    target_ordinal = _get_ordinal(target_context)

    # Query snapshots for this item
    query = select(Snapshot).where(Snapshot.item_id == item_id)
    if source_id:
        query = query.where(Snapshot.source_id == source_id)

    result = await db.execute(query)
    snapshots = result.scalars().all()

    if not snapshots:
        return None

    # Load contexts for all snapshots
    snapshot_context_ids = {s.context_id for s in snapshots}
    for ctx_id in snapshot_context_ids:
        if ctx_id not in contexts_cache:
            ctx_item = await _get_item_or_404(db, ctx_id, "Context")
            contexts_cache[ctx_id] = ctx_item

    # Filter to snapshots at or before target ordinal, then pick the most recent
    candidates = []
    for snap in snapshots:
        snap_ctx = contexts_cache.get(snap.context_id)
        if snap_ctx:
            snap_ordinal = _get_ordinal(snap_ctx)
            if snap_ordinal <= target_ordinal:
                candidates.append((snap, snap_ordinal))

    if not candidates:
        return None

    # Sort by ordinal (descending) and return the first (most recent)
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


async def _get_effective_values_at_context_all_sources(
    db: AsyncSession,
    item_id: uuid.UUID,
    context_id: uuid.UUID,
    contexts_cache: dict[uuid.UUID, Item] | None = None,
) -> dict[uuid.UUID, Snapshot]:
    """
    Get effective snapshots from all sources for an item at a context.

    Returns a dict mapping source_id → Snapshot.
    Uses the carry-forward logic: the most recent snapshot from each
    source at or before the context ordinal.
    """
    if contexts_cache is None:
        contexts_cache = {}

    # Get or fetch the target context
    if context_id not in contexts_cache:
        ctx_item = await _get_item_or_404(db, context_id, "Context")
        contexts_cache[context_id] = ctx_item
    target_context = contexts_cache[context_id]
    target_ordinal = _get_ordinal(target_context)

    # Get all snapshots for this item
    result = await db.execute(select(Snapshot).where(Snapshot.item_id == item_id))
    snapshots = result.scalars().all()

    if not snapshots:
        return {}

    # Load contexts for all snapshots
    snapshot_context_ids = {s.context_id for s in snapshots}
    for ctx_id in snapshot_context_ids:
        if ctx_id not in contexts_cache:
            ctx_item = await _get_item_or_404(db, ctx_id, "Context")
            contexts_cache[ctx_id] = ctx_item

    # Group by source, filter to snapshots at or before target ordinal
    by_source: dict[uuid.UUID, list[tuple[Snapshot, int]]] = defaultdict(list)
    for snap in snapshots:
        snap_ctx = contexts_cache.get(snap.context_id)
        if snap_ctx:
            snap_ordinal = _get_ordinal(snap_ctx)
            if snap_ordinal <= target_ordinal:
                by_source[snap.source_id].append((snap, snap_ordinal))

    # Pick the most recent from each source
    effective: dict[uuid.UUID, Snapshot] = {}
    for src_id, candidates in by_source.items():
        candidates.sort(key=lambda x: x[1], reverse=True)
        effective[src_id] = candidates[0][0]

    return effective


def _build_property_changes(
    old_properties: dict,
    new_properties: dict,
    item_id: uuid.UUID,
    from_context: uuid.UUID,
    to_context: uuid.UUID,
    source_id: uuid.UUID | None = None,
    old_effective_context: uuid.UUID | None = None,
    new_effective_context: uuid.UUID | None = None,
) -> list[PropertyChange]:
    """
    Detect property-level changes between two property dicts.

    Returns list of PropertyChange objects for properties that differ.

    In cumulative mode, old_effective_context and new_effective_context
    indicate which milestone the values actually came from (for carry-forward values).
    """
    changes = []

    # Collect all property names from both dicts
    all_keys = set(old_properties.keys()) | set(new_properties.keys())

    for prop_name in sorted(all_keys):
        old_val = old_properties.get(prop_name)
        new_val = new_properties.get(prop_name)

        # Skip if values match — use values_match which handles
        # type normalization (string "914.4" vs float 914.4),
        # case-insensitive comparison, and dimension tolerance.
        if values_match(
            str(old_val) if old_val is not None else None,
            str(new_val) if new_val is not None else None,
            property_name=prop_name,
        ):
            continue

        changes.append(
            PropertyChange(
                property_name=prop_name,
                old_value=old_val,
                new_value=new_val,
                from_context=from_context,
                to_context=to_context,
                source=source_id,
                old_effective_context=str(old_effective_context)
                if old_effective_context
                else None,
                new_effective_context=str(new_effective_context)
                if new_effective_context
                else None,
            )
        )

    return changes


async def _categorize_items_with_source_filter(
    db: AsyncSession,
    item_ids: list[uuid.UUID],
    from_context_id: uuid.UUID,
    to_context_id: uuid.UUID,
    source_id: uuid.UUID,
    mode: str = "cumulative",
    contexts_cache: dict[uuid.UUID, Item] | None = None,
) -> tuple[list[ItemComparison], ComparisonSummary]:
    """
    Compare items with a specific source filter.

    Only looks at snapshots from the given source. An item is:
    - added: exists at to_context but not from_context (from this source)
    - removed: exists at from_context but not to_context (from this source)
    - modified: exists at both but values differ
    - unchanged: exists at both and values match

    Mode 'cumulative': use carry-forward semantics with effective contexts.
    Mode 'submitted': use strict context_id matching (no carry-forward).
    """
    if contexts_cache is None:
        contexts_cache = {}

    items_data = {}
    result = await db.execute(select(Item).where(Item.id.in_(item_ids)))
    for item in result.scalars().all():
        items_data[item.id] = item

    comparisons = []
    added_count = 0
    removed_count = 0
    modified_count = 0
    unchanged_count = 0

    for item_id in item_ids:
        item = items_data.get(item_id)
        if not item:
            continue

        # Get snapshots from the source at both contexts
        if mode == "submitted":
            # Strict context_id match
            from_snap = await _get_snapshot_at_context_submitted(
                db, item_id, from_context_id, source_id
            )
            to_snap = await _get_snapshot_at_context_submitted(
                db, item_id, to_context_id, source_id
            )
            old_effective_context = None
            new_effective_context = None
        else:  # cumulative (default)
            # Carry-forward with effective contexts
            from_snap = await _get_effective_snapshot_at_context(
                db, item_id, from_context_id, source_id, contexts_cache
            )
            to_snap = await _get_effective_snapshot_at_context(
                db, item_id, to_context_id, source_id, contexts_cache
            )
            # In cumulative mode, the effective context is where the snapshot actually came from
            old_effective_context = from_snap.context_id if from_snap else None
            new_effective_context = to_snap.context_id if to_snap else None

        from_exists = from_snap is not None
        to_exists = to_snap is not None

        if not from_exists and not to_exists:
            # Neither exists from this source — skip
            continue
        elif not from_exists and to_exists:
            # Added
            category = "added"
            added_count += 1
            changes = []
        elif from_exists and not to_exists:
            # Removed
            category = "removed"
            removed_count += 1
            changes = []
        else:
            # Both exist — check if modified
            changes = _build_property_changes(
                from_snap.properties,
                to_snap.properties,
                item_id,
                from_context_id,
                to_context_id,
                source_id,
                old_effective_context=old_effective_context,
                new_effective_context=new_effective_context,
            )
            if changes:
                category = "modified"
                modified_count += 1
            else:
                category = "unchanged"
                unchanged_count += 1

        comparisons.append(
            ItemComparison(
                item_id=item_id,
                identifier=item.identifier,
                item_type=item.item_type,
                category=category,
                changes=changes,
            )
        )

    total = added_count + removed_count + modified_count + unchanged_count
    summary = ComparisonSummary(
        added=added_count,
        removed=removed_count,
        modified=modified_count,
        unchanged=unchanged_count,
        total=total,
    )

    return comparisons, summary


async def _categorize_items_with_submitted_mode_all_sources(
    db: AsyncSession,
    item_ids: list[uuid.UUID],
    from_context_id: uuid.UUID,
    to_context_id: uuid.UUID,
) -> tuple[list[ItemComparison], ComparisonSummary]:
    """
    Compare items using submitted mode (strict context_id matching) without source filter.

    For each source, gets the snapshot at exactly the context (no carry-forward).
    Then merges properties from all sources at the exact context.

    An item is:
    - added: has snapshots at to_context but not from_context
    - removed: has snapshots at from_context but not to_context
    - modified: has snapshots at both but values differ
    - unchanged: has snapshots at both and values match
    """
    items_data = {}
    result = await db.execute(select(Item).where(Item.id.in_(item_ids)))
    for item in result.scalars().all():
        items_data[item.id] = item

    comparisons = []
    added_count = 0
    removed_count = 0
    modified_count = 0
    unchanged_count = 0

    # Get all snapshots at both contexts to find which items have snapshots
    from_snapshots_query = select(Snapshot).where(
        (Snapshot.item_id.in_(item_ids)) & (Snapshot.context_id == from_context_id)
    )
    to_snapshots_query = select(Snapshot).where(
        (Snapshot.item_id.in_(item_ids)) & (Snapshot.context_id == to_context_id)
    )

    from_result = await db.execute(from_snapshots_query)
    from_snapshots = from_result.scalars().all()

    to_result = await db.execute(to_snapshots_query)
    to_snapshots = to_result.scalars().all()

    # Index snapshots by item_id
    from_snaps_by_item: dict[uuid.UUID, list[Snapshot]] = defaultdict(list)
    to_snaps_by_item: dict[uuid.UUID, list[Snapshot]] = defaultdict(list)

    for snap in from_snapshots:
        from_snaps_by_item[snap.item_id].append(snap)

    for snap in to_snapshots:
        to_snaps_by_item[snap.item_id].append(snap)

    for item_id in item_ids:
        item = items_data.get(item_id)
        if not item:
            continue

        from_snaps = from_snaps_by_item.get(item_id, [])
        to_snaps = to_snaps_by_item.get(item_id, [])

        from_exists = bool(from_snaps)
        to_exists = bool(to_snaps)

        if not from_exists and not to_exists:
            # Neither exists — skip
            continue
        elif not from_exists and to_exists:
            # Added
            category = "added"
            added_count += 1
            changes = []
        elif from_exists and not to_exists:
            # Removed
            category = "removed"
            removed_count += 1
            changes = []
        else:
            # Both exist — merge properties from all sources and check if modified
            from_properties = {}
            for snap in from_snaps:
                from_properties.update(snap.properties)

            to_properties = {}
            for snap in to_snaps:
                to_properties.update(snap.properties)

            changes = _build_property_changes(
                from_properties,
                to_properties,
                item_id,
                from_context_id,
                to_context_id,
                source_id=None,  # No single source
                old_effective_context=None,
                new_effective_context=None,
            )

            if changes:
                category = "modified"
                modified_count += 1
            else:
                category = "unchanged"
                unchanged_count += 1

        comparisons.append(
            ItemComparison(
                item_id=item_id,
                identifier=item.identifier,
                item_type=item.item_type,
                category=category,
                changes=changes,
            )
        )

    total = added_count + removed_count + modified_count + unchanged_count
    summary = ComparisonSummary(
        added=added_count,
        removed=removed_count,
        modified=modified_count,
        unchanged=unchanged_count,
        total=total,
    )

    return comparisons, summary


async def _categorize_items_with_effective_values(
    db: AsyncSession,
    item_ids: list[uuid.UUID],
    from_context_id: uuid.UUID,
    to_context_id: uuid.UUID,
    mode: str = "cumulative",
    contexts_cache: dict[uuid.UUID, Item] | None = None,
) -> tuple[list[ItemComparison], ComparisonSummary]:
    """
    Compare items using effective values from all sources.

    For each source, gets the most recent snapshot at or before each context.
    Then merges properties from all sources.

    An item is:
    - added: has effective values at to_context but not from_context
    - removed: has effective values at from_context but not to_context
    - modified: has effective values at both but they differ
    - unchanged: has effective values at both and they match

    Mode 'cumulative': use carry-forward with per-property effective contexts.
    """
    if contexts_cache is None:
        contexts_cache = {}

    items_data = {}
    result = await db.execute(select(Item).where(Item.id.in_(item_ids)))
    for item in result.scalars().all():
        items_data[item.id] = item

    comparisons = []
    added_count = 0
    removed_count = 0
    modified_count = 0
    unchanged_count = 0

    for item_id in item_ids:
        item = items_data.get(item_id)
        if not item:
            continue

        # Get effective values from all sources at both contexts
        from_effective = await _get_effective_values_at_context_all_sources(
            db, item_id, from_context_id, contexts_cache
        )
        to_effective = await _get_effective_values_at_context_all_sources(
            db, item_id, to_context_id, contexts_cache
        )

        # Merge properties from all sources
        from_properties = {}
        from_property_contexts: dict[str, uuid.UUID] = {}
        for snap in from_effective.values():
            for prop_name, value in snap.properties.items():
                from_properties[prop_name] = value
                from_property_contexts[prop_name] = snap.context_id

        to_properties = {}
        to_property_contexts: dict[str, uuid.UUID] = {}
        for snap in to_effective.values():
            for prop_name, value in snap.properties.items():
                to_properties[prop_name] = value
                to_property_contexts[prop_name] = snap.context_id

        from_exists = bool(from_effective)
        to_exists = bool(to_effective)

        if not from_exists and not to_exists:
            # Neither exists — skip
            continue
        elif not from_exists and to_exists:
            # Added
            category = "added"
            added_count += 1
            changes = []
        elif from_exists and not to_exists:
            # Removed
            category = "removed"
            removed_count += 1
            changes = []
        else:
            # Both exist — check if modified
            # Only report changes for properties that actually exist in both contexts
            # In cumulative mode, a property that disappears in later context should not show as changed
            # unless it actually got updated to a different value
            changes = []
            all_props = set(from_properties.keys()) | set(to_properties.keys())

            for prop_name in sorted(all_props):
                from_val = from_properties.get(prop_name)
                to_val = to_properties.get(prop_name)

                # Skip if both absent or values match
                if from_val is None and to_val is None:
                    continue

                if values_match(
                    str(from_val) if from_val is not None else None,
                    str(to_val) if to_val is not None else None,
                    property_name=prop_name,
                ):
                    continue

                # Only report as changed if both have values (not if one is absent)
                # because absence in cumulative mode means carry-forward
                if from_val is not None and to_val is not None:
                    change = PropertyChange(
                        property_name=prop_name,
                        old_value=from_val,
                        new_value=to_val,
                        from_context=from_context_id,
                        to_context=to_context_id,
                        source=None,
                        old_effective_context=str(
                            from_property_contexts.get(prop_name)
                        ),
                        new_effective_context=str(to_property_contexts.get(prop_name)),
                    )
                    changes.append(change)

            if changes:
                category = "modified"
                modified_count += 1
            else:
                category = "unchanged"
                unchanged_count += 1

        comparisons.append(
            ItemComparison(
                item_id=item_id,
                identifier=item.identifier,
                item_type=item.item_type,
                category=category,
                changes=changes,
            )
        )

    total = added_count + removed_count + modified_count + unchanged_count
    summary = ComparisonSummary(
        added=added_count,
        removed=removed_count,
        modified=modified_count,
        unchanged=unchanged_count,
        total=total,
    )

    return comparisons, summary


# ─── Main Route ────────────────────────────────────────────────


@router.post("/compare", response_model=ComparisonResult, status_code=200)
async def compare_snapshots(
    payload: ComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare item snapshots across two milestones.

    Supports two modes:
    1. Compare specific items (item_ids)
    2. Compare all children of a parent item (parent_item_id)

    If source_filter is provided, only compares that source's snapshots.
    Otherwise, uses effective values from all sources.

    Returns paginated results with per-item and summary statistics.
    """
    # Validate that exactly one of item_ids or parent_item_id is provided
    if (payload.item_ids is None and payload.parent_item_id is None) or (
        payload.item_ids is not None and payload.parent_item_id is not None
    ):
        raise HTTPException(
            status_code=400,
            detail="Specify exactly one of: item_ids (list) or parent_item_id (single)",
        )

    # Validate both contexts are milestones
    from_context = await _validate_context(db, payload.from_context_id)
    to_context = await _validate_context(db, payload.to_context_id)

    # Determine the list of items to compare
    if payload.item_ids is not None:
        item_ids = payload.item_ids
        # Check project access via first item if available
        if item_ids:
            project_id = await get_project_for_item(db, item_ids[0])
            if project_id:
                await require_project_access(db, project_id, current_user)
    else:
        # Get children of parent
        item_ids = await _get_children_of_parent(db, payload.parent_item_id)
        # Check project access via parent item
        project_id = await get_project_for_item(db, payload.parent_item_id)
        if project_id:
            await require_project_access(db, project_id, current_user)

    if not item_ids:
        # No items to compare
        empty_summary = ComparisonSummary(
            added=0, removed=0, modified=0, unchanged=0, total=0
        )
        return ComparisonResult(
            from_context=ItemSummary(
                id=from_context.id,
                item_type=from_context.item_type,
                identifier=from_context.identifier,
            ),
            to_context=ItemSummary(
                id=to_context.id,
                item_type=to_context.item_type,
                identifier=to_context.identifier,
            ),
            items=[],
            summary=empty_summary,
            limit=payload.limit,
            offset=payload.offset,
        )

    # Cache for contexts to avoid repeated queries
    contexts_cache = {
        from_context.id: from_context,
        to_context.id: to_context,
    }

    # Perform comparison
    if payload.source_filter:
        # Validate source exists
        await _get_item_or_404(db, payload.source_filter, "Source")
        comparisons, summary = await _categorize_items_with_source_filter(
            db,
            item_ids,
            payload.from_context_id,
            payload.to_context_id,
            payload.source_filter,
            mode=payload.mode,
            contexts_cache=contexts_cache,
        )
    else:
        # No source filter: compare all sources
        if payload.mode == "submitted":
            # Submitted mode: strict context_id matching, no carry-forward
            (
                comparisons,
                summary,
            ) = await _categorize_items_with_submitted_mode_all_sources(
                db,
                item_ids,
                payload.from_context_id,
                payload.to_context_id,
            )
        else:
            # Cumulative mode (default): carry-forward with effective contexts
            comparisons, summary = await _categorize_items_with_effective_values(
                db,
                item_ids,
                payload.from_context_id,
                payload.to_context_id,
                mode=payload.mode,
                contexts_cache=contexts_cache,
            )

    # Apply pagination
    paginated_items = comparisons[payload.offset : payload.offset + payload.limit]

    return ComparisonResult(
        from_context=ItemSummary(
            id=from_context.id,
            item_type=from_context.item_type,
            identifier=from_context.identifier,
        ),
        to_context=ItemSummary(
            id=to_context.id,
            item_type=to_context.item_type,
            identifier=to_context.identifier,
        ),
        items=paginated_items,
        summary=summary,
        limit=payload.limit,
        offset=payload.offset,
    )
