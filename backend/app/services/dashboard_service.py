"""
Dashboard and rollup service — WP-13a.

Query logic for project health, import summaries, temporal trends,
and directive status rollups.  Pure data operations — no HTTP concerns.

Architecture notes:
  - Uses Python-side JSONB filtering for SQLite test compatibility
    (cannot use PostgreSQL JSONB operators in unit tests).
  - All queries are project-scoped via the connection graph:
    project → building → floor → room → door.
"""

import uuid
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.type_config import get_type_config
from app.models.core import Connection, Item, Snapshot


# ─── Helpers ──────────────────────────────────────────────────


async def _get_project_item_ids(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> set[uuid.UUID]:
    """
    Get all item IDs belonging to a project via connections.

    Two-phase traversal:
      1. BFS forward from project to find base items
         (spatial hierarchy, sources, milestones).
      2. Reverse lookup to find items that connect INTO those
         base items (workflow items: conflicts, changes, directives,
         decisions, import_batches).

    Returns the full set of item IDs including the project itself.
    """
    # Phase 1: BFS forward from project
    visited: set[uuid.UUID] = {project_id}
    frontier = {project_id}

    while frontier:
        result = await db.execute(
            select(Connection.target_item_id).where(
                Connection.source_item_id.in_(frontier)
            )
        )
        new_targets = {row[0] for row in result.all()} - visited
        visited |= new_targets
        frontier = new_targets

    base_ids = set(visited)

    # Phase 2: reverse lookup — items that connect TO base items
    reverse_result = await db.execute(
        select(Connection.source_item_id).where(Connection.target_item_id.in_(base_ids))
    )
    reverse_ids = {row[0] for row in reverse_result.all()}
    visited |= reverse_ids

    return visited


# ─── Project Health ──────────────────────────────────────────


async def get_project_health(
    db: AsyncSession,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Build project health summary.

    Counts all items by type, plus action item breakdowns
    by property, source pair, and affected item type.

    GET /api/v1/dashboard/health?project=uuid
    """
    # Fetch items (optionally scoped to project)
    if project_id:
        item_ids = await _get_project_item_ids(db, project_id)
        result = await db.execute(select(Item).where(Item.id.in_(item_ids)))
    else:
        result = await db.execute(select(Item))

    all_items = list(result.scalars().all())

    # ── Total items by type ───────────────────────────────────
    by_type: dict[str, int] = {}
    for item in all_items:
        by_type[item.item_type] = by_type.get(item.item_type, 0) + 1

    # ── Action item counts ────────────────────────────────────
    unresolved_changes = 0
    unresolved_conflicts = 0
    pending_directives = 0
    fulfilled_directives = 0
    decisions_made = 0

    by_property: dict[str, dict[str, int]] = {}
    by_affected_type: dict[str, int] = {}

    # Index items by id for fast lookup
    items_by_id: dict[uuid.UUID, Item] = {item.id: item for item in all_items}

    for item in all_items:
        status = (item.properties.get("status") or "").lower()
        prop_name = item.properties.get("property_name")

        if item.item_type == "change" and status in ("detected", "acknowledged"):
            unresolved_changes += 1
            if prop_name:
                entry = by_property.setdefault(
                    prop_name, {"changes": 0, "conflicts": 0, "directives": 0}
                )
                entry["changes"] += 1

        elif item.item_type == "conflict" and status == "detected":
            unresolved_conflicts += 1
            if prop_name:
                entry = by_property.setdefault(
                    prop_name, {"changes": 0, "conflicts": 0, "directives": 0}
                )
                entry["conflicts"] += 1

        elif item.item_type == "directive":
            if status == "pending":
                pending_directives += 1
                if prop_name:
                    entry = by_property.setdefault(
                        prop_name, {"changes": 0, "conflicts": 0, "directives": 0}
                    )
                    entry["directives"] += 1
            elif status == "fulfilled":
                fulfilled_directives += 1

        elif item.item_type == "decision":
            decisions_made += 1

    # ── by_affected_type: count action items by the type of item they affect ─
    by_affected_type: dict[str, dict[str, int]] = {}

    workflow_types = ("change", "conflict", "directive")
    workflow_items = [i for i in all_items if i.item_type in workflow_types]

    for wf_item in workflow_items:
        status = (wf_item.properties.get("status") or "").lower()
        is_active = (
            (wf_item.item_type == "change" and status in ("detected", "acknowledged"))
            or (wf_item.item_type == "conflict" and status == "detected")
            or (wf_item.item_type == "directive" and status == "pending")
        )
        if not is_active:
            continue

        # Find subject via affected_item_id property (generic, not category-filtered)
        affected_id_str = wf_item.properties.get(
            "affected_item_id"
        ) or wf_item.properties.get("affected_item")
        if not affected_id_str:
            continue

        try:
            affected_id = uuid.UUID(affected_id_str)
        except (ValueError, TypeError):
            continue

        affected = items_by_id.get(affected_id)
        if not affected:
            continue

        entry = by_affected_type.setdefault(
            affected.item_type, {"changes": 0, "conflicts": 0, "directives": 0}
        )
        if wf_item.item_type == "change":
            entry["changes"] += 1
        elif wf_item.item_type == "conflict":
            entry["conflicts"] += 1
        elif wf_item.item_type == "directive":
            entry["directives"] += 1

    # ── by_source_pair: conflict counts by source pair ────────
    by_source_pair: dict[str, int] = {}
    conflict_items = [
        i
        for i in all_items
        if i.item_type == "conflict"
        and (i.properties.get("status") or "").lower() == "detected"
    ]

    if conflict_items:
        conflict_ids = [c.id for c in conflict_items]
        conn_result = await db.execute(
            select(Connection).where(Connection.source_item_id.in_(conflict_ids))
        )
        conflict_connections = list(conn_result.scalars().all())

        for conflict in conflict_items:
            # Gather source items connected to this conflict
            connected_target_ids = [
                c.target_item_id
                for c in conflict_connections
                if c.source_item_id == conflict.id
            ]
            source_names: list[str] = []
            for tid in connected_target_ids:
                target = items_by_id.get(tid)
                if target:
                    tc = get_type_config(target.item_type)
                    if tc and tc.is_source_type:
                        source_names.append(target.identifier or target.item_type)

            if len(source_names) >= 2:
                source_names.sort()
                pair_key = "+".join(source_names)
                by_source_pair[pair_key] = by_source_pair.get(pair_key, 0) + 1

    return {
        "total_items": len(all_items),
        "by_type": by_type,
        "action_items": {
            "unresolved_changes": unresolved_changes,
            "unresolved_conflicts": unresolved_conflicts,
            "pending_directives": pending_directives,
            "fulfilled_directives": fulfilled_directives,
            "decisions_made": decisions_made,
        },
        "by_property": {
            k: {
                "changes": v["changes"],
                "conflicts": v["conflicts"],
                "directives": v["directives"],
            }
            for k, v in by_property.items()
        },
        "by_source_pair": {k: {"conflicts": v} for k, v in by_source_pair.items()},
        "by_affected_type": {
            k: {
                "changes": v["changes"],
                "conflicts": v["conflicts"],
                "directives": v["directives"],
            }
            for k, v in by_affected_type.items()
        },
    }


# ─── Import Summary ─────────────────────────────────────────


async def get_import_summary(
    db: AsyncSession,
    project_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Get import summary for the most recent batch (or a specific batch).

    Reconstructs summary data from import_batch items and their
    stored properties (populated by the import pipeline).

    GET /api/v1/dashboard/import-summary?project=uuid
    """
    # Find import batches
    query = select(Item).where(Item.item_type == "import_batch")

    if batch_id:
        query = query.where(Item.id == batch_id)

    query = query.order_by(Item.created_at.desc())
    result = await db.execute(query)
    batches = list(result.scalars().all())

    if not batches:
        return {
            "batch_id": None,
            "batch_identifier": None,
            "source_id": None,
            "source_identifier": None,
            "context_id": None,
            "context_identifier": None,
            "imported_at": None,
            "source_changes": 0,
            "affected_items": 0,
            "new_conflicts": 0,
            "resolved_conflicts": 0,
            "directives_fulfilled": 0,
            "items_imported": 0,
            "by_source": [],
        }

    # If project-scoped, filter batches connected to project items
    if project_id:
        project_item_ids = await _get_project_item_ids(db, project_id)
        batches = [b for b in batches if _batch_related_to_project(b, project_item_ids)]
        if not batches:
            return {
                "batch_id": None,
                "batch_identifier": None,
                "source_id": None,
                "source_identifier": None,
                "context_id": None,
                "context_identifier": None,
                "imported_at": None,
                "source_changes": 0,
                "affected_items": 0,
                "new_conflicts": 0,
                "resolved_conflicts": 0,
                "directives_fulfilled": 0,
                "items_imported": 0,
                "by_source": [],
            }

    batch = batches[0]  # Most recent
    props = batch.properties or {}

    # Resolve source and context identifiers
    source_id_str = props.get("source_item_id")
    context_id_str = props.get("time_context_id")
    source_identifier = None
    context_identifier = None

    if source_id_str:
        try:
            src_result = await db.execute(
                select(Item).where(Item.id == uuid.UUID(source_id_str))
            )
            src_item = src_result.scalar_one_or_none()
            if src_item:
                source_identifier = src_item.identifier
        except (ValueError, TypeError):
            pass

    if context_id_str:
        try:
            ctx_result = await db.execute(
                select(Item).where(Item.id == uuid.UUID(context_id_str))
            )
            ctx_item = ctx_result.scalar_one_or_none()
            if ctx_item:
                context_identifier = ctx_item.identifier
        except (ValueError, TypeError):
            pass

    # Extract summary fields from batch properties
    return {
        "batch_id": batch.id,
        "batch_identifier": batch.identifier,
        "source_id": uuid.UUID(source_id_str) if source_id_str else None,
        "source_identifier": source_identifier,
        "context_id": uuid.UUID(context_id_str) if context_id_str else None,
        "context_identifier": context_identifier,
        "imported_at": batch.created_at.isoformat() if batch.created_at else None,
        "source_changes": _safe_int(props.get("source_changes", 0)),
        "affected_items": _safe_int(props.get("affected_items", 0)),
        "new_conflicts": _safe_int(props.get("new_conflicts", 0)),
        "resolved_conflicts": _safe_int(props.get("resolved_conflicts", 0)),
        "directives_fulfilled": _safe_int(props.get("directives_fulfilled", 0)),
        "items_imported": _safe_int(props.get("items_imported", 0)),
        "by_source": [],  # Populated when multi-source imports are implemented
    }


def _batch_related_to_project(
    batch: Item,
    project_item_ids: set[uuid.UUID],
) -> bool:
    """Check if a batch's source item belongs to the project."""
    source_id_str = (batch.properties or {}).get("source_item_id")
    if source_id_str:
        try:
            return uuid.UUID(source_id_str) in project_item_ids
        except (ValueError, TypeError):
            pass
    return False


def _safe_int(val: Any) -> int:
    """Safely convert a value to int."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


# ─── Temporal Trend ──────────────────────────────────────────


async def get_temporal_trend(
    db: AsyncSession,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Action item counts at each milestone over time.

    For each milestone: how many changes, conflicts, and directives
    were detected/resolved/fulfilled at that point in time.

    GET /api/v1/dashboard/temporal-trend?project=uuid
    """
    # Fetch milestones ordered by ordinal
    result = await db.execute(select(Item).where(Item.item_type == "milestone"))
    milestones = list(result.scalars().all())

    # Sort by ordinal (Python-side for SQLite compat)
    milestones.sort(key=lambda m: _safe_int(m.properties.get("ordinal", 0)))

    if not milestones:
        return {"milestones": []}

    # Fetch all workflow items
    workflow_types = ("change", "conflict", "directive")
    wf_result = await db.execute(select(Item).where(Item.item_type.in_(workflow_types)))
    workflow_items = list(wf_result.scalars().all())

    if not workflow_items:
        return {
            "milestones": [
                {
                    "context_id": m.id,
                    "context_identifier": m.identifier,
                    "ordinal": _safe_int(m.properties.get("ordinal", 0)),
                    "changes": 0,
                    "conflicts": 0,
                    "directives": 0,
                    "resolved_conflicts": 0,
                    "fulfilled_directives": 0,
                }
                for m in milestones
            ],
        }

    # Get connections from workflow items to milestones
    workflow_ids = [i.id for i in workflow_items]
    milestone_ids = [m.id for m in milestones]

    conn_result = await db.execute(
        select(Connection).where(
            Connection.source_item_id.in_(workflow_ids),
            Connection.target_item_id.in_(milestone_ids),
        )
    )
    connections = list(conn_result.scalars().all())

    # Also check snapshots — workflow items may be linked to milestones
    # via their snapshot context_id
    snap_result = await db.execute(
        select(Snapshot).where(
            Snapshot.item_id.in_(workflow_ids),
            Snapshot.context_id.in_(milestone_ids),
        )
    )
    snapshots = list(snap_result.scalars().all())

    # Build item → milestone mapping from both connections and snapshots
    item_to_milestones: dict[uuid.UUID, set[uuid.UUID]] = {}
    for conn in connections:
        item_to_milestones.setdefault(conn.source_item_id, set()).add(
            conn.target_item_id
        )
    for snap in snapshots:
        item_to_milestones.setdefault(snap.item_id, set()).add(snap.context_id)

    # Build per-milestone counts
    milestone_data: dict[uuid.UUID, dict[str, int]] = {
        m.id: {
            "changes": 0,
            "conflicts": 0,
            "directives": 0,
            "resolved_conflicts": 0,
            "fulfilled_directives": 0,
        }
        for m in milestones
    }

    for wf_item in workflow_items:
        linked_milestones = item_to_milestones.get(wf_item.id, set())
        status = (wf_item.properties.get("status") or "").lower()

        for ms_id in linked_milestones:
            if ms_id not in milestone_data:
                continue
            counts = milestone_data[ms_id]

            if wf_item.item_type == "change":
                counts["changes"] += 1
            elif wf_item.item_type == "conflict":
                counts["conflicts"] += 1
                if status in ("resolved", "resolved_by_agreement"):
                    counts["resolved_conflicts"] += 1
            elif wf_item.item_type == "directive":
                counts["directives"] += 1
                if status == "fulfilled":
                    counts["fulfilled_directives"] += 1

    return {
        "milestones": [
            {
                "context_id": m.id,
                "context_identifier": m.identifier,
                "ordinal": _safe_int(m.properties.get("ordinal", 0)),
                **milestone_data[m.id],
            }
            for m in milestones
        ],
    }


# ─── Directive Status Rollup ────────────────────────────────


async def get_directive_status(
    db: AsyncSession,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Directive status grouped by target source.

    For each source that has pending/fulfilled directives,
    returns the count of each.

    GET /api/v1/dashboard/directive-status?project=uuid
    """
    # Fetch all directives
    result = await db.execute(select(Item).where(Item.item_type == "directive"))
    all_directives = list(result.scalars().all())

    total_pending = 0
    total_fulfilled = 0

    # Group by target_source_id
    by_source: dict[str, dict[str, int]] = {}

    for d in all_directives:
        status = (d.properties.get("status") or "").lower()
        target_source_id = d.properties.get("target_source_id", "unknown")

        if target_source_id not in by_source:
            by_source[target_source_id] = {"pending": 0, "fulfilled": 0}

        if status == "pending":
            total_pending += 1
            by_source[target_source_id]["pending"] += 1
        elif status == "fulfilled":
            total_fulfilled += 1
            by_source[target_source_id]["fulfilled"] += 1

    # Resolve source identifiers
    source_rollups: list[dict[str, Any]] = []
    for source_id_str, counts in by_source.items():
        source_identifier = None
        source_uuid = None
        try:
            source_uuid = uuid.UUID(source_id_str)
            src_result = await db.execute(select(Item).where(Item.id == source_uuid))
            src_item = src_result.scalar_one_or_none()
            if src_item:
                source_identifier = src_item.identifier
        except (ValueError, TypeError):
            pass

        source_rollups.append(
            {
                "source_id": source_uuid or source_id_str,
                "source_identifier": source_identifier,
                "pending": counts["pending"],
                "fulfilled": counts["fulfilled"],
            }
        )

    return {
        "total_pending": total_pending,
        "total_fulfilled": total_fulfilled,
        "by_source": source_rollups,
    }


# ─── Graph-Based Property Rollup ──────────────────────────────


async def get_action_items_by_property_graph(
    db: AsyncSession,
    project_id: uuid.UUID | None = None,
) -> dict[str, dict[str, int]]:
    """
    Rollup action items by property using graph connections.

    Alternative to the string-based by_property dict in get_project_health().
    Uses property items + connections instead of JSONB property_name strings.

    SQLite-compatible: loads data in bulk, aggregates in Python.

    Returns: {
        "door/fire_rating": {"changes": 2, "conflicts": 1, "directives": 1},
        ...
    }
    """
    # 1. Load all property items
    prop_result = await db.execute(select(Item).where(Item.item_type == "property"))
    property_items = {p.id: p for p in prop_result.scalars().all()}

    if not property_items:
        return {}

    # 2. Load all workflow items
    workflow_types = ("change", "conflict", "directive")
    wf_result = await db.execute(select(Item).where(Item.item_type.in_(workflow_types)))
    workflow_items = {w.id: w for w in wf_result.scalars().all()}

    if not workflow_items:
        return {}

    # 3. Load connections from workflow → property
    conn_result = await db.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id.in_(workflow_items.keys()),
                Connection.target_item_id.in_(property_items.keys()),
            )
        )
    )
    connections = conn_result.scalars().all()

    # 4. Aggregate in Python
    rollup: dict[str, dict[str, int]] = {}
    for conn in connections:
        prop_item = property_items.get(conn.target_item_id)
        wf_item = workflow_items.get(conn.source_item_id)
        if not prop_item or not wf_item:
            continue

        prop_id = prop_item.identifier
        if prop_id not in rollup:
            rollup[prop_id] = {"changes": 0, "conflicts": 0, "directives": 0}

        # Only count active statuses
        status = (wf_item.properties.get("status") or "").lower()
        if wf_item.item_type == "change" and status in ("detected", "acknowledged"):
            rollup[prop_id]["changes"] += 1
        elif wf_item.item_type == "conflict" and status == "detected":
            rollup[prop_id]["conflicts"] += 1
        elif wf_item.item_type == "directive" and status == "pending":
            rollup[prop_id]["directives"] += 1

    return rollup


# ─── Affected Items for Workflow Perspective ──────────────


async def get_affected_items(
    db: AsyncSession,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Get affected item summaries for the workflow perspective.

    Returns all items in the project that have workflow actions
    (changes, conflicts, directives), grouped by item_type, with per-item
    action_counts.

    GET /api/v1/dashboard/affected-items?project=uuid
    """
    # Phase 1: Get all items in the project (or all items globally)
    if project_id:
        item_ids = await _get_project_item_ids(db, project_id)
        result = await db.execute(select(Item).where(Item.id.in_(item_ids)))
    else:
        result = await db.execute(select(Item))

    all_items = list(result.scalars().all())
    items_by_id: dict[uuid.UUID, Item] = {item.id: item for item in all_items}

    # Phase 2: Find all workflow items
    workflow_types = ("change", "conflict", "directive")
    workflow_items = [i for i in all_items if i.item_type in workflow_types]

    if not workflow_items:
        return {"groups": []}

    # Phase 3: Build per-item action counts using affected_item_id property
    item_action_counts: dict[uuid.UUID, dict[str, int]] = {}

    for wf_item in workflow_items:
        status = (wf_item.properties.get("status") or "").lower()
        is_active = (
            (wf_item.item_type == "change" and status in ("detected", "acknowledged"))
            or (wf_item.item_type == "conflict" and status == "detected")
            or (wf_item.item_type == "directive" and status == "pending")
        )
        if not is_active:
            continue

        # Find subject via affected_item_id property
        affected_id_str = wf_item.properties.get(
            "affected_item_id"
        ) or wf_item.properties.get("affected_item")
        if not affected_id_str:
            continue

        try:
            affected_id = uuid.UUID(affected_id_str)
        except (ValueError, TypeError):
            continue

        if affected_id not in items_by_id:
            continue

        if affected_id not in item_action_counts:
            item_action_counts[affected_id] = {
                "changes": 0,
                "conflicts": 0,
                "directives": 0,
            }

        if wf_item.item_type == "change":
            item_action_counts[affected_id]["changes"] += 1
        elif wf_item.item_type == "conflict":
            item_action_counts[affected_id]["conflicts"] += 1
        elif wf_item.item_type == "directive":
            item_action_counts[affected_id]["directives"] += 1

    # Phase 4: Group by item_type
    groups_dict: dict[str, dict[str, Any]] = {}

    for affected_id, action_counts in item_action_counts.items():
        affected_item = items_by_id.get(affected_id)
        if not affected_item:
            continue

        item_type = affected_item.item_type
        if item_type not in groups_dict:
            tc = get_type_config(item_type)
            groups_dict[item_type] = {
                "item_type": item_type,
                "label": tc.plural_label if tc else item_type,
                "items": [],
            }

        groups_dict[item_type]["items"].append(
            {
                "id": affected_id,
                "identifier": affected_item.identifier,
                "item_type": item_type,
                "action_counts": action_counts,
            }
        )

    # Phase 5: Build final response
    groups = []
    for item_type in sorted(groups_dict.keys()):
        group = groups_dict[item_type]
        groups.append(
            {
                "item_type": item_type,
                "label": group["label"],
                "count": len(group["items"]),
                "items": group["items"],
            }
        )

    return {"groups": groups}
