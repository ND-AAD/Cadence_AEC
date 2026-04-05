"""
Resolution workflow service — WP-12a.

Core business logic for conflict resolution, change acknowledgment,
and directive management.  Pure data operations — no HTTP concerns.

Architecture (workplan Decisions 8, 9, 10):
  Decision 8 — resolution snapshot source_id = decision_item_id
  Decision 9 — new source disagreement creates new conflict
  Decision 10 — import pipeline auto-fulfills pending directives
"""

import uuid
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.type_config import get_type_config
from app.models.core import Connection, Item, Snapshot
from app.services.normalization import values_match
from app.services.property_service import get_or_create_property_item


# ─── Helpers ──────────────────────────────────────────────────


async def _get_connected_items_by_type(
    db: AsyncSession,
    source_item_id: uuid.UUID,
    target_type: str | None = None,
    exclude_types: set[str] | None = None,
) -> list[Item]:
    """Get items connected FROM source_item (outgoing connections)."""
    query = (
        select(Item)
        .join(Connection, Connection.target_item_id == Item.id)
        .where(Connection.source_item_id == source_item_id)
    )
    if target_type:
        query = query.where(Item.item_type == target_type)
    if exclude_types:
        query = query.where(Item.item_type.notin_(exclude_types))

    result = await db.execute(query)
    return list(result.scalars().all())


async def _find_conflict_sources(
    db: AsyncSession,
    conflict_item: Item,
) -> list[Item]:
    """
    Find the document sources connected to a conflict.

    A conflict has connections to: affected_item, source1, source2, milestone.
    We want the document sources (types with is_source_type=True).
    """
    connected = await _get_connected_items_by_type(db, conflict_item.id)
    sources = []
    for item in connected:
        tc = get_type_config(item.item_type)
        if tc and tc.is_source_type:
            sources.append(item)
    return sources


async def _find_conflict_affected_item(
    db: AsyncSession,
    conflict_item: Item,
) -> Item | None:
    """Find the affected item connected to a conflict.

    The affected item is the one that is NOT a source, context, or workflow type.
    After DYN-0, spatial types live in firm vocabulary (not ITEM_TYPES), so we
    identify the affected item by exclusion: it's the connected item whose type
    is not recognized as source, context, or workflow in the OS registry.
    """
    connected = await _get_connected_items_by_type(db, conflict_item.id)
    for item in connected:
        tc = get_type_config(item.item_type)
        # If the type is in OS config, skip source/context/workflow types
        if tc:
            if tc.is_source_type or tc.is_context_type or tc.category == "workflow":
                continue
            # OS type that's not source/context/workflow — could be affected item
            # but organization/definition types shouldn't be conflict targets
            if tc.category in ("organization", "definition", "temporal"):
                continue
            return item
        else:
            # Type not in OS config — it's a firm vocabulary type (spatial),
            # which is the affected item we're looking for.
            return item
    return None


async def _find_conflict_milestone(
    db: AsyncSession,
    conflict_item: Item,
) -> Item | None:
    """Find the milestone connected to a conflict."""
    connected = await _get_connected_items_by_type(
        db, conflict_item.id, target_type="milestone"
    )
    return connected[0] if connected else None


async def _ensure_connection(
    db: AsyncSession,
    source_item_id: uuid.UUID,
    target_item_id: uuid.UUID,
    properties: dict | None = None,
) -> Connection:
    """Create connection if it doesn't already exist."""
    result = await db.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id == source_item_id,
                Connection.target_item_id == target_item_id,
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    conn = Connection(
        source_item_id=source_item_id,
        target_item_id=target_item_id,
        properties=properties or {},
    )
    db.add(conn)
    await db.flush()
    return conn


# ─── Conflict Resolution ─────────────────────────────────────


async def resolve_conflict(
    db: AsyncSession,
    conflict_item: Item,
    chosen_value: str | None,
    chosen_source_id: uuid.UUID | None,
    method: str,
    rationale: str,
    decided_by: str,
) -> tuple[Item, list[Item]]:
    """
    Resolve a conflict, creating a decision and directives.

    Implements Decision 8: resolution snapshot uses source_id = decision_item_id.

    Steps:
      1. Create decision item with self-sourced snapshot
      2. Create resolution snapshot ON THE CONFLICT with source_id = decision.id
      3. Update conflict status to "resolved"
      4. Connect decision → conflict
      5. Create directives for non-chosen sources

    Args:
        db: Database session
        conflict_item: The conflict item to resolve
        chosen_value: The resolved value
        chosen_source_id: UUID of the source whose value wins (for chosen_source method)
        method: Resolution method ("chosen_source" or "manual_value")
        rationale: Why this resolution was chosen
        decided_by: Who decided

    Returns:
        (decision_item, list_of_directive_items)

    Raises:
        ValueError: If conflict is already resolved or invalid
    """
    # Validate status
    current_status = conflict_item.properties.get("status", "")
    if current_status in ("resolved", "resolved_by_agreement"):
        raise ValueError(f"Conflict is already resolved (status: {current_status})")

    # Gather related items
    affected_item = await _find_conflict_affected_item(db, conflict_item)
    if not affected_item:
        raise ValueError("Cannot find affected item for this conflict")

    milestone = await _find_conflict_milestone(db, conflict_item)
    if not milestone:
        raise ValueError("Cannot find milestone for this conflict")

    sources = await _find_conflict_sources(db, conflict_item)
    if not sources:
        raise ValueError("Cannot find sources for this conflict")

    property_name = conflict_item.properties.get("property_name", "")

    # If method is chosen_source, resolve the chosen_value from the source's snapshot
    if method == "chosen_source" and chosen_source_id and chosen_value is None:
        # Look up the chosen source's effective value
        snap_result = await db.execute(
            select(Snapshot).where(
                and_(
                    Snapshot.item_id == affected_item.id,
                    Snapshot.source_id == chosen_source_id,
                )
            )
        )
        chosen_snap = snap_result.scalars().first()
        if chosen_snap:
            chosen_value = chosen_snap.properties.get(property_name)

    # ── Step 1: Create decision item ──────────────────────────
    decision_item = Item(
        item_type="decision",
        identifier=f"Decision: {conflict_item.identifier}",
        properties={
            "rationale": rationale,
            "resolved_value": chosen_value,
            "decided_by": decided_by,
            "method": method,
            "chosen_source_id": str(chosen_source_id) if chosen_source_id else None,
            "conflict_item_id": str(conflict_item.id),
            "affected_item_id": str(affected_item.id),
            "property_name": property_name,
        },
    )
    db.add(decision_item)
    await db.flush()
    await db.refresh(decision_item)

    # Decision self-sourced snapshot: (decision, milestone, decision)
    decision_snap = Snapshot(
        item_id=decision_item.id,
        context_id=milestone.id,
        source_id=decision_item.id,
        properties={
            "rationale": rationale,
            "resolved_value": chosen_value,
            "decided_by": decided_by,
            "method": method,
            "chosen_source_id": str(chosen_source_id) if chosen_source_id else None,
        },
    )
    db.add(decision_snap)
    await db.flush()

    # ── Step 2: Resolution snapshot ON the conflict ───────────
    # Decision 8: source_id = decision_item_id
    resolution_snap = Snapshot(
        item_id=conflict_item.id,
        context_id=milestone.id,
        source_id=decision_item.id,  # ← Decision 8
        properties={
            "status": "resolved",
            "resolved_value": chosen_value,
            "method": method,
            "chosen_source_id": str(chosen_source_id) if chosen_source_id else None,
            "decided_by": decided_by,
        },
    )
    db.add(resolution_snap)
    await db.flush()

    # ── Step 3: Update conflict status ────────────────────────
    conflict_item.properties = {
        **conflict_item.properties,
        "status": "resolved",
    }
    await db.flush()

    # ── Step 4: Connection: decision → conflict ───────────────
    await _ensure_connection(db, decision_item.id, conflict_item.id)

    # ── Step 5: Create directives for non-chosen sources ──────
    directive_items: list[Item] = []

    for source in sources:
        if chosen_source_id and source.id == chosen_source_id:
            continue  # Skip the winning source

        # Check if this source's effective value already matches
        source_snap_result = await db.execute(
            select(Snapshot).where(
                and_(
                    Snapshot.item_id == affected_item.id,
                    Snapshot.source_id == source.id,
                )
            )
        )
        source_snaps = source_snap_result.scalars().all()

        # Find the effective snapshot (most recent by milestone ordinal)
        effective_value = None
        if source_snaps:
            # Load contexts for ordinal lookup
            context_ids = {s.context_id for s in source_snaps}
            contexts_result = await db.execute(
                select(Item).where(Item.id.in_(context_ids))
            )
            contexts = {c.id: c for c in contexts_result.scalars().all()}

            best_ordinal = -1
            milestone_ordinal = int(milestone.properties.get("ordinal", 0))
            for snap in source_snaps:
                ctx = contexts.get(snap.context_id)
                if not ctx:
                    continue
                try:
                    snap_ord = int(ctx.properties.get("ordinal", 0))
                except (ValueError, TypeError):
                    continue
                if snap_ord <= milestone_ordinal and snap_ord > best_ordinal:
                    best_ordinal = snap_ord
                    effective_value = snap.properties.get(property_name)

        # Skip directive if source's value already matches the resolution
        already_matches = False
        if effective_value is not None and chosen_value is not None:
            already_matches = values_match(
                str(effective_value), str(chosen_value), property_name
            )

        if already_matches:
            continue  # Source already has the correct value — no directive needed

        # Create directive item
        directive = Item(
            item_type="directive",
            identifier=f"Directive: {affected_item.identifier} / {property_name} → {source.identifier}",
            properties={
                "property_name": property_name,
                "target_value": chosen_value,
                "target_source_id": str(source.id),
                "decision_item_id": str(decision_item.id),
                "affected_item_id": str(affected_item.id),
                "status": "pending",
            },
        )
        db.add(directive)
        await db.flush()
        await db.refresh(directive)

        # Directive self-sourced snapshot: (directive, milestone, directive)
        directive_snap = Snapshot(
            item_id=directive.id,
            context_id=milestone.id,
            source_id=directive.id,
            properties={
                "property_name": property_name,
                "target_value": chosen_value,
                "target_source_id": str(source.id),
                "status": "pending",
            },
        )
        db.add(directive_snap)
        await db.flush()

        # 4 connections: directive → affected_item, target_source, decision, milestone
        await _ensure_connection(db, directive.id, affected_item.id)
        await _ensure_connection(
            db, directive.id, source.id, {"relationship": "target_source"}
        )
        await _ensure_connection(
            db, directive.id, decision_item.id, {"relationship": "created_by"}
        )
        await _ensure_connection(
            db, directive.id, milestone.id, {"relationship": "context"}
        )

        # Connect directive to property item
        prop_item, _ = await get_or_create_property_item(
            db, affected_item.item_type, property_name
        )
        await _ensure_connection(db, directive.id, prop_item.id)

        directive_items.append(directive)

    return decision_item, directive_items


# ─── Change Acknowledgment ───────────────────────────────────


async def acknowledge_change(
    db: AsyncSession,
    change_item: Item,
    property_name: str | None = None,
) -> None:
    """
    Acknowledge a detected change, optionally for a specific property.

    When property_name is provided, only that property is marked as
    acknowledged. The change item transitions to "acknowledged" only
    when ALL properties have been individually acknowledged.

    When property_name is None, acknowledges the entire change item
    (all properties at once).

    Args:
        change_item: The change item to acknowledge
        property_name: Optional specific property to acknowledge

    Raises:
        ValueError: If item is not a change or has invalid status
    """
    if change_item.item_type != "change":
        raise ValueError(f"Item is not a change (type: {change_item.item_type})")

    current_status = (change_item.properties.get("status") or "").lower()
    if current_status == "acknowledged":
        return  # Idempotent

    props = dict(change_item.properties)

    if property_name:
        # Per-property acknowledgment
        acknowledged_props = set(props.get("acknowledged_properties") or [])
        acknowledged_props.add(property_name)
        props["acknowledged_properties"] = sorted(acknowledged_props)

        # Check if all properties in the changes dict are now acknowledged
        changes_dict = props.get("changes") or {}
        all_acknowledged = all(k in acknowledged_props for k in changes_dict)

        if all_acknowledged:
            props["status"] = "acknowledged"

        change_item.properties = props
    else:
        # Acknowledge entire change item
        change_item.properties = {
            **props,
            "status": "acknowledged",
        }

    # Update self-sourced snapshot
    snap_result = await db.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == change_item.id,
                Snapshot.source_id == change_item.id,
            )
        )
    )
    snap = snap_result.scalar_one_or_none()
    if snap:
        snap.properties = {
            **snap.properties,
            "status": "acknowledged",
        }

    await db.flush()


# ─── Directive Fulfillment ───────────────────────────────────


async def fulfill_directive(
    db: AsyncSession,
    directive_item: Item,
) -> None:
    """
    Mark a directive as fulfilled.

    Args:
        directive_item: The directive item to fulfill

    Raises:
        ValueError: If item is not a directive or already fulfilled
    """
    if directive_item.item_type != "directive":
        raise ValueError(f"Item is not a directive (type: {directive_item.item_type})")

    current_status = directive_item.properties.get("status", "")
    if current_status == "fulfilled":
        return  # Idempotent

    # Update item properties
    directive_item.properties = {
        **directive_item.properties,
        "status": "fulfilled",
    }

    # Update self-sourced snapshot
    snap_result = await db.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == directive_item.id,
                Snapshot.source_id == directive_item.id,
            )
        )
    )
    snap = snap_result.scalar_one_or_none()
    if snap:
        snap.properties = {
            **snap.properties,
            "status": "fulfilled",
        }

    await db.flush()


# ─── Status Transitions (Decision 13) ────────────────────────

# Valid workflow item types for status transitions.
_WORKFLOW_TYPES = {"change", "conflict", "directive"}

# Valid transitions per action.
_START_REVIEW_FROM = {"detected"}
_HOLD_FROM = {"detected", "in_review", "pending"}
_RESUME_FROM = {"hold"}


async def _transition_status(
    db: AsyncSession,
    item: Item,
    new_status: str,
    valid_from: set[str],
    action_label: str,
    *,
    store_pre_hold: bool = False,
    restore_pre_hold: bool = False,
) -> str:
    """
    Generic status transition on a workflow item.

    Updates both the item properties and the self-sourced snapshot.

    Args:
        item: Workflow item (change, conflict, or directive)
        new_status: Target status
        valid_from: Set of statuses that allow this transition
        action_label: Human label for error messages
        store_pre_hold: If True, save current status as pre_hold_status
        restore_pre_hold: If True, restore pre_hold_status instead of new_status

    Returns:
        The previous status string.

    Raises:
        ValueError: If item type or current status doesn't permit the transition.
    """
    if item.item_type not in _WORKFLOW_TYPES:
        raise ValueError(
            f"{action_label} only applies to workflow items "
            f"(change/conflict/directive). Got: {item.item_type}"
        )

    current_status = (item.properties.get("status") or "").lower()
    if current_status not in valid_from:
        raise ValueError(
            f"Cannot {action_label} from status '{current_status}'. "
            f"Valid source statuses: {valid_from}"
        )

    previous_status = current_status

    # Determine the actual new status.
    if restore_pre_hold:
        pre_hold = item.properties.get("pre_hold_status", "detected")
        new_status = pre_hold

    # Build updated properties.
    updated_props = {**item.properties, "status": new_status}
    if store_pre_hold:
        updated_props["pre_hold_status"] = current_status
    if restore_pre_hold:
        updated_props.pop("pre_hold_status", None)

    item.properties = updated_props

    # Update self-sourced snapshot.
    snap_result = await db.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == item.id,
                Snapshot.source_id == item.id,
            )
        )
    )
    snap = snap_result.scalar_one_or_none()
    if snap:
        snap.properties = {**snap.properties, "status": new_status}

    await db.flush()
    return previous_status


async def start_review(
    db: AsyncSession,
    item: Item,
) -> str:
    """
    Transition a workflow item from detected → in_review.

    Signals to the team that someone is actively examining this item.
    DS-2 §6.3: "Start Review" only on Surface 2 (workflow item view).

    Returns:
        Previous status.
    """
    return await _transition_status(
        db, item, "in_review", _START_REVIEW_FROM, "start review"
    )


async def hold_item(
    db: AsyncSession,
    item: Item,
) -> str:
    """
    Place a workflow item on hold.

    Stores the pre-hold status so resume can restore it.
    DS-2 §6.5: Hold from any active state; pip shifts to filed color.

    Returns:
        Previous status.
    """
    return await _transition_status(
        db,
        item,
        "hold",
        _HOLD_FROM,
        "hold",
        store_pre_hold=True,
    )


async def resume_review(
    db: AsyncSession,
    item: Item,
) -> str:
    """
    Resume a held workflow item.

    Restores the pre-hold status (detected or in_review).
    DS-2 §6.5: Resume reverses hold.

    Returns:
        Previous status (hold).
    """
    return await _transition_status(
        db,
        item,
        "",
        _RESUME_FROM,
        "resume review",
        restore_pre_hold=True,
    )


# ─── Action Item Queries ─────────────────────────────────────


async def get_action_items_rollup(
    db: AsyncSession,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Get counts of pending action items across all workflow types.

    Uses Python-side filtering (not JSONB SQL operators) for
    SQLite test compatibility.

    Returns dict with: changes_pending, conflicts_pending, directives_pending,
    total_action_items, by_type, by_property.
    """
    # Load all workflow items
    workflow_types = ("change", "conflict", "directive")
    result = await db.execute(select(Item).where(Item.item_type.in_(workflow_types)))
    all_items = result.scalars().all()

    changes_pending = 0
    conflicts_pending = 0
    directives_pending = 0
    by_property: dict[str, dict[str, int]] = {}

    for item in all_items:
        status = (item.properties.get("status") or "").lower()
        prop_name = item.properties.get("property_name", "unknown")

        if prop_name not in by_property:
            by_property[prop_name] = {"changes": 0, "conflicts": 0, "directives": 0}

        if item.item_type == "change" and status in ("detected", "acknowledged"):
            changes_pending += 1
            by_property[prop_name]["changes"] += 1
        elif item.item_type == "conflict" and status == "detected":
            conflicts_pending += 1
            by_property[prop_name]["conflicts"] += 1
        elif item.item_type == "directive" and status == "pending":
            directives_pending += 1
            by_property[prop_name]["directives"] += 1

    total = changes_pending + conflicts_pending + directives_pending

    return {
        "changes_pending": changes_pending,
        "conflicts_pending": conflicts_pending,
        "directives_pending": directives_pending,
        "total_action_items": total,
        "by_type": {
            "changes": changes_pending,
            "conflicts": conflicts_pending,
            "directives": directives_pending,
        },
        "by_property": by_property,
    }


async def list_directives(
    db: AsyncSession,
    source_id: uuid.UUID | None = None,
    property_name: str | None = None,
    status: str | None = None,
) -> tuple[list[Item], dict[str, int]]:
    """
    List directives with optional filtering.

    Returns:
        (list_of_directive_items, pending_by_source_dict)
    """
    result = await db.execute(
        select(Item)
        .where(Item.item_type == "directive")
        .order_by(Item.created_at.desc())
    )
    all_directives = result.scalars().all()

    # Python-side filtering (SQLite compat)
    filtered: list[Item] = []
    pending_by_source: dict[str, int] = {}

    for d in all_directives:
        # Apply filters
        if source_id and d.properties.get("target_source_id") != str(source_id):
            continue
        if property_name and d.properties.get("property_name") != property_name:
            continue
        if status and d.properties.get("status") != status:
            continue
        filtered.append(d)

        # Aggregate pending by source
        if d.properties.get("status") == "pending":
            src = d.properties.get("target_source_id", "unknown")
            pending_by_source[src] = pending_by_source.get(src, 0) + 1

    return filtered, pending_by_source
