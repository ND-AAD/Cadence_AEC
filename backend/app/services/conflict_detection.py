"""
Shared conflict detection logic — WP-18.0.

Extracted from import_service.py to support both schedule import
and spec propagation pipelines.

Core functions:
  - get_or_create_conflict: Idempotent conflict item creation (Decision 9)
  - get_effective_snapshots: Get other sources' effective values for an item
  - detect_conflicts_for_item: Compare one item's new values against other sources
  - detect_conflicts_batch: Run detection across multiple items
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.type_config import get_conflict_excluded_types
from app.models.core import Connection, Item, Snapshot
from app.services.normalization import values_match
from app.services.property_service import get_or_create_property_item


# ─── Result Types ────────────────────────────────────────────


@dataclass
class ConflictResult:
    """Result of conflict detection for a single property disagreement."""
    conflict_item: Item
    is_new: bool
    affected_item_id: uuid.UUID
    affected_item_identifier: str | None
    property_name: str
    values: dict[str, str | None]  # source_identifier → value
    context_id: uuid.UUID


@dataclass
class AutoResolutionResult:
    """Result of an auto-resolution when sources agree on a prior conflict."""
    conflict_item: Item
    property_name: str


@dataclass
class DetectionSummary:
    """Aggregate results from a batch detection run."""
    new_conflicts: int = 0
    resolved_conflicts: int = 0
    conflicts: list[ConflictResult] = field(default_factory=list)
    auto_resolutions: list[AutoResolutionResult] = field(default_factory=list)


# ─── Core Functions ──────────────────────────────────────────


async def get_or_create_conflict(
    db: AsyncSession,
    affected_item: Item,
    property_path: str,
    source_a_id: uuid.UUID,
    source_b_id: uuid.UUID,
) -> tuple[Item, bool]:
    """
    Get or create a conflict item for (affected_item, property, source_pair).

    Per Decision 9: each unique (item, property, source_pair) produces
    a distinct conflict item. Source pair canonicalized by sorting UUIDs.

    Returns:
        (conflict_item, is_new)
    """
    pair = sorted([str(source_a_id), str(source_b_id)])
    pair_suffix = f"{pair[0][:8]}+{pair[1][:8]}"
    identifier = f"{affected_item.identifier} / {property_path} / {pair_suffix}"

    # Look for existing conflict with matching identifier
    result = await db.execute(
        select(Item).where(
            and_(
                Item.item_type == "conflict",
                Item.identifier == identifier,
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False

    # Create new conflict item
    conflict = Item(
        item_type="conflict",
        identifier=identifier,
        properties={
            "property_name": property_path,
            "status": "detected",
            "affected_item": str(affected_item.id),
            "source_a": str(source_a_id),
            "source_b": str(source_b_id),
        },
    )
    db.add(conflict)
    await db.flush()
    await db.refresh(conflict)
    return conflict, True


async def get_effective_snapshots(
    db: AsyncSession,
    item_id: uuid.UUID,
    current_source_id: uuid.UUID,
    context_ordinal: int,
) -> dict[uuid.UUID, Snapshot]:
    """
    Get the effective snapshot from each OTHER source for an item.

    For each source (excluding the current source and workflow types),
    find the most recent snapshot at or before the context ordinal.

    Args:
        db: Database session
        item_id: The item to check snapshots for
        current_source_id: The source making the new assertion (excluded)
        context_ordinal: The ordinal of the current milestone

    Returns:
        Dict mapping source_id → most recent Snapshot at or before context_ordinal
    """
    # Get all snapshots for this item
    result = await db.execute(
        select(Snapshot).where(Snapshot.item_id == item_id)
    )
    all_snaps = result.scalars().all()

    # Load source items to filter workflow types
    source_ids = {s.source_id for s in all_snaps}
    if not source_ids:
        return {}

    sources_result = await db.execute(select(Item).where(Item.id.in_(source_ids)))
    sources = {s.id: s for s in sources_result.scalars().all()}

    # Load context items for ordinal lookup
    context_ids = {s.context_id for s in all_snaps}
    contexts_result = await db.execute(select(Item).where(Item.id.in_(context_ids)))
    contexts = {c.id: c for c in contexts_result.scalars().all()}

    excluded_types = get_conflict_excluded_types()

    # Group by source, filter to other document sources
    effective: dict[uuid.UUID, Snapshot] = {}
    for snap in all_snaps:
        # Skip current source
        if snap.source_id == current_source_id:
            continue
        # Skip types excluded from conflict detection (per TypeConfig)
        src = sources.get(snap.source_id)
        if not src or src.item_type in excluded_types:
            continue
        # Check ordinal
        ctx = contexts.get(snap.context_id)
        if not ctx:
            continue
        snap_ordinal = ctx.properties.get("ordinal", 0) if ctx.properties else 0
        try:
            snap_ordinal = int(snap_ordinal)
        except (ValueError, TypeError):
            continue
        if snap_ordinal > context_ordinal:
            continue

        existing = effective.get(snap.source_id)
        if existing is None:
            effective[snap.source_id] = snap
        else:
            existing_ctx = contexts.get(existing.context_id)
            existing_ord = 0
            if existing_ctx and existing_ctx.properties:
                try:
                    existing_ord = int(existing_ctx.properties.get("ordinal", 0))
                except (ValueError, TypeError):
                    pass
            if snap_ordinal > existing_ord:
                effective[snap.source_id] = snap

    return effective


async def _ensure_connection_exists(
    db: AsyncSession,
    source_item_id: uuid.UUID,
    target_item_id: uuid.UUID,
    properties: dict | None = None,
) -> None:
    """Create connection if it doesn't already exist."""
    result = await db.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id == source_item_id,
                Connection.target_item_id == target_item_id,
            )
        )
    )
    if not result.scalar_one_or_none():
        db.add(Connection(
            source_item_id=source_item_id,
            target_item_id=target_item_id,
            properties=properties or {},
        ))
        await db.flush()


async def detect_conflicts_for_item(
    db: AsyncSession,
    item: Item,
    source_id: uuid.UUID,
    context: Item,
    snapshot_properties: dict,
) -> tuple[list[ConflictResult], list[AutoResolutionResult]]:
    """
    Compare this source's values against other sources' effective values
    for the given item. Create conflict items where they disagree.
    Auto-resolve conflicts where they now agree.

    Args:
        db: Database session
        item: The item being asserted on (e.g., Door 101)
        source_id: The source making the new assertion
        context: The milestone context item
        snapshot_properties: The new property values from this source

    Returns:
        (list of ConflictResults, list of AutoResolutionResults)
    """
    context_ordinal = context.properties.get("ordinal", 0) if context.properties else 0
    try:
        context_ordinal = int(context_ordinal)
    except (ValueError, TypeError):
        context_ordinal = 0

    # Get effective snapshots from other sources
    other_effective = await get_effective_snapshots(
        db, item.id, source_id, context_ordinal
    )

    if not other_effective:
        return [], []

    # Load source items for identifier display
    other_source_ids = set(other_effective.keys())
    other_sources_result = await db.execute(
        select(Item).where(Item.id.in_(other_source_ids))
    )
    other_sources = {s.id: s for s in other_sources_result.scalars().all()}

    # Also load current source for identifier
    current_source_result = await db.execute(
        select(Item).where(Item.id == source_id)
    )
    current_source = current_source_result.scalar_one_or_none()
    current_source_identifier = current_source.identifier if current_source else str(source_id)

    conflicts: list[ConflictResult] = []
    auto_resolutions: list[AutoResolutionResult] = []

    for other_source_id, other_snap in other_effective.items():
        other_source = other_sources.get(other_source_id)
        other_source_identifier = other_source.identifier if other_source else str(other_source_id)

        for prop_name, new_value in snapshot_properties.items():
            other_value = other_snap.properties.get(prop_name)

            if other_value is None:
                continue  # Other source doesn't address this property

            if not values_match(str(new_value), str(other_value), property_name=prop_name):
                # Disagreement — create or get conflict item
                conflict_item, is_new = await get_or_create_conflict(
                    db, item, prop_name, source_id, other_source_id
                )

                # Upsert conflict snapshot: (what=conflict, when=milestone, who=conflict)
                existing_conflict_snap = await db.execute(
                    select(Snapshot).where(
                        and_(
                            Snapshot.item_id == conflict_item.id,
                            Snapshot.context_id == context.id,
                            Snapshot.source_id == conflict_item.id,
                        )
                    )
                )
                existing_cs = existing_conflict_snap.scalar_one_or_none()
                conflict_snap_props = {
                    "status": "DETECTED",
                    "property_path": prop_name,
                    "values": {
                        str(current_source_identifier): str(new_value),
                        str(other_source_identifier): str(other_value),
                    },
                    "affected_item": str(item.id),
                }
                if existing_cs:
                    existing_cs.properties = conflict_snap_props
                    await db.flush()
                else:
                    db.add(Snapshot(
                        item_id=conflict_item.id,
                        context_id=context.id,
                        source_id=conflict_item.id,
                        properties=conflict_snap_props,
                    ))
                    await db.flush()

                # Ensure connections: conflict → affected_item, both sources, milestone
                for target_id in [item.id, source_id, other_source_id, context.id]:
                    await _ensure_connection_exists(db, conflict_item.id, target_id)

                # Connect conflict to property item
                prop_item, _ = await get_or_create_property_item(
                    db, item.item_type, prop_name
                )
                await _ensure_connection_exists(db, conflict_item.id, prop_item.id)

                conflicts.append(ConflictResult(
                    conflict_item=conflict_item,
                    is_new=is_new,
                    affected_item_id=item.id,
                    affected_item_identifier=item.identifier,
                    property_name=prop_name,
                    values={
                        str(current_source_identifier): str(new_value),
                        str(other_source_identifier): str(other_value),
                    },
                    context_id=context.id,
                ))

            else:
                # Agreement — check if this resolves an existing conflict
                pair = sorted([str(source_id), str(other_source_id)])
                pair_suffix = f"{pair[0][:8]}+{pair[1][:8]}"
                conflict_identifier = f"{item.identifier} / {prop_name} / {pair_suffix}"
                existing_conflict_result = await db.execute(
                    select(Item).where(
                        and_(
                            Item.item_type == "conflict",
                            Item.identifier == conflict_identifier,
                        )
                    )
                )
                existing_conflict = existing_conflict_result.scalar_one_or_none()
                if existing_conflict:
                    if existing_conflict.properties.get("status") == "detected":
                        # Auto-resolve: create resolution snapshot
                        resolution_snap_result = await db.execute(
                            select(Snapshot).where(
                                and_(
                                    Snapshot.item_id == existing_conflict.id,
                                    Snapshot.context_id == context.id,
                                    Snapshot.source_id == existing_conflict.id,
                                )
                            )
                        )
                        existing_res = resolution_snap_result.scalar_one_or_none()
                        resolution_props = {
                            "status": "RESOLVED_BY_AGREEMENT",
                            "property_path": prop_name,
                            "agreed_value": str(new_value),
                        }
                        if existing_res:
                            existing_res.properties = resolution_props
                        else:
                            db.add(Snapshot(
                                item_id=existing_conflict.id,
                                context_id=context.id,
                                source_id=existing_conflict.id,
                                properties=resolution_props,
                            ))
                        # Update conflict status
                        existing_conflict.properties = {
                            **existing_conflict.properties,
                            "status": "resolved_by_agreement",
                        }
                        await db.flush()

                        auto_resolutions.append(AutoResolutionResult(
                            conflict_item=existing_conflict,
                            property_name=prop_name,
                        ))

    return conflicts, auto_resolutions


async def detect_conflicts_batch(
    db: AsyncSession,
    items_with_snapshots: list[tuple[Item, uuid.UUID, Item, dict]],
) -> DetectionSummary:
    """
    Run conflict detection for a batch of items.

    Used by both import_service (schedule import) and propagation_service
    (spec propagation).

    Args:
        items_with_snapshots: List of (item, source_id, context, snapshot_properties)
            - item: The element being asserted on
            - source_id: The source making the assertion
            - context: The milestone context item
            - snapshot_properties: The new property values

    Returns:
        DetectionSummary with aggregate counts and detailed results
    """
    summary = DetectionSummary()

    for item, source_id, context, snapshot_properties in items_with_snapshots:
        conflicts, auto_resolutions = await detect_conflicts_for_item(
            db, item, source_id, context, snapshot_properties
        )

        for cr in conflicts:
            if cr.is_new:
                summary.new_conflicts += 1
            summary.conflicts.append(cr)

        for ar in auto_resolutions:
            summary.resolved_conflicts += 1
            summary.auto_resolutions.append(ar)

    return summary
