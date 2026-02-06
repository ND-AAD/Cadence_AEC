"""
Import pipeline service — WP-6.

Parses Excel/CSV files, matches rows to items by identifier,
creates source-attributed snapshots, and tracks import batches.

Key flow:
  1. Parse file → list of rows with identifier + properties
  2. Match each row: exact → normalized → fuzzy (with pg_trgm)
  3. Create items for unmatched rows (or queue for user confirmation)
  4. Create snapshot per matched/created item: (item, milestone, source)
  5. Create source self-snapshot with import metadata
  6. Create connections: source → target for each imported item

Single-writer enforcement: one import at a time per project (advisory).
"""

import csv
import io
import re
import uuid
from typing import Any

import openpyxl
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.type_config import get_type_config
from app.models.core import Connection, Item, Snapshot
from app.schemas.imports import (
    ChangeItemResult,
    ConflictItemResult,
    ConfirmMatchResponse,
    ImportMappingConfig,
    ImportResult,
    ImportSummary,
    MatchCandidate,
    UnmatchedRow,
)
from app.services.normalization import (
    normalize_case,
    normalize_dimension_to_inches,
    normalize_identifier,
    normalize_numeric,
    normalize_whitespace,
    values_match,
)


# ─── Normalization Registry ───────────────────────────────────

SYSTEM_NORMALIZATIONS = {
    "lowercase_trim": lambda v: normalize_case(normalize_whitespace(str(v))),
    "imperial_door_dimensions": lambda v: str(normalize_dimension_to_inches(str(v)) or v),
    "numeric": lambda v: normalize_numeric(str(v)),
}


# ─── File Parsing ─────────────────────────────────────────────

def _strip_to_alphanum(s: str) -> str:
    """Strip all non-alphanumeric characters and lowercase. Used for identifier matching."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse_excel(
    file_bytes: bytes,
    mapping: ImportMappingConfig,
) -> list[dict[str, Any]]:
    """
    Parse an Excel file into a list of row dicts.

    Each dict has:
      - _identifier: the raw identifier value from the identifier column
      - _row_number: 1-indexed row number in the spreadsheet
      - property_name: value ... (one per mapped column)
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    # Skip to header row
    for _ in range(mapping.header_row - 1):
        next(rows_iter, None)
    header_row_values = next(rows_iter, None)
    if not header_row_values:
        return []

    headers = [str(h).strip() if h is not None else "" for h in header_row_values]

    # Build column index lookup
    col_indices: dict[str, int] = {}
    for idx, h in enumerate(headers):
        col_indices[h] = idx

    # Locate identifier column
    id_col_idx = col_indices.get(mapping.identifier_column)
    if id_col_idx is None:
        # Try case-insensitive match
        lower_map = {k.lower(): v for k, v in col_indices.items()}
        id_col_idx = lower_map.get(mapping.identifier_column.lower())
    if id_col_idx is None:
        raise ValueError(
            f"Identifier column '{mapping.identifier_column}' not found in headers: {headers}"
        )

    # Build property column indices
    prop_col_indices: dict[str, int] = {}
    for col_name, prop_name in mapping.property_mapping.items():
        cidx = col_indices.get(col_name)
        if cidx is None:
            lower_map = {k.lower(): v for k, v in col_indices.items()}
            cidx = lower_map.get(col_name.lower())
        if cidx is not None:
            prop_col_indices[prop_name] = cidx

    # Parse data rows
    parsed: list[dict[str, Any]] = []
    row_num = mapping.header_row + 1  # 1-indexed, first data row
    for row_values in rows_iter:
        # Skip empty rows
        if not row_values or all(v is None for v in row_values):
            row_num += 1
            continue

        identifier_val = row_values[id_col_idx] if id_col_idx < len(row_values) else None
        if identifier_val is None or str(identifier_val).strip() == "":
            row_num += 1
            continue

        record: dict[str, Any] = {
            "_identifier": str(identifier_val).strip(),
            "_row_number": row_num,
        }

        for prop_name, cidx in prop_col_indices.items():
            val = row_values[cidx] if cidx < len(row_values) else None
            if val is not None:
                # Apply normalization if configured
                norm_type = mapping.normalizations.get(prop_name)
                if norm_type and norm_type in SYSTEM_NORMALIZATIONS:
                    val = SYSTEM_NORMALIZATIONS[norm_type](val)
                record[prop_name] = str(val).strip() if val is not None else None

        parsed.append(record)
        row_num += 1

    wb.close()
    return parsed


def parse_csv(
    file_bytes: bytes,
    mapping: ImportMappingConfig,
) -> list[dict[str, Any]]:
    """Parse a CSV file into a list of row dicts (same shape as parse_excel)."""
    text_content = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text_content))

    # Skip to header row
    for _ in range(mapping.header_row - 1):
        next(reader, None)
    header_row_values = next(reader, None)
    if not header_row_values:
        return []

    headers = [h.strip() for h in header_row_values]

    col_indices: dict[str, int] = {}
    for idx, h in enumerate(headers):
        col_indices[h] = idx

    id_col_idx = col_indices.get(mapping.identifier_column)
    if id_col_idx is None:
        lower_map = {k.lower(): v for k, v in col_indices.items()}
        id_col_idx = lower_map.get(mapping.identifier_column.lower())
    if id_col_idx is None:
        raise ValueError(
            f"Identifier column '{mapping.identifier_column}' not found in headers: {headers}"
        )

    prop_col_indices: dict[str, int] = {}
    for col_name, prop_name in mapping.property_mapping.items():
        cidx = col_indices.get(col_name)
        if cidx is None:
            lower_map = {k.lower(): v for k, v in col_indices.items()}
            cidx = lower_map.get(col_name.lower())
        if cidx is not None:
            prop_col_indices[prop_name] = cidx

    parsed: list[dict[str, Any]] = []
    row_num = mapping.header_row + 1
    for row_values in reader:
        if not row_values or all(v.strip() == "" for v in row_values):
            row_num += 1
            continue

        identifier_val = row_values[id_col_idx] if id_col_idx < len(row_values) else None
        if identifier_val is None or identifier_val.strip() == "":
            row_num += 1
            continue

        record: dict[str, Any] = {
            "_identifier": identifier_val.strip(),
            "_row_number": row_num,
        }

        for prop_name, cidx in prop_col_indices.items():
            val = row_values[cidx] if cidx < len(row_values) else None
            if val is not None and val.strip():
                norm_type = mapping.normalizations.get(prop_name)
                if norm_type and norm_type in SYSTEM_NORMALIZATIONS:
                    val = SYSTEM_NORMALIZATIONS[norm_type](val)
                record[prop_name] = val.strip()

        parsed.append(record)
        row_num += 1

    return parsed


# ─── Identifier Matching ──────────────────────────────────────

async def match_item(
    db: AsyncSession,
    raw_identifier: str,
    item_type: str,
    project_id: uuid.UUID | None = None,
) -> tuple[Item | None, str]:
    """
    Match a raw identifier to an existing item.

    Returns (item, confidence) where confidence is:
      - 'exact': identifier matches exactly
      - 'normalized': matches after stripping non-alphanumeric + lowering
      - 'none': no match found

    Fuzzy matching (pg_trgm) is not available in SQLite tests,
    so it's handled separately in the route layer for production.
    """
    # 1. Exact match
    query = select(Item).where(
        and_(
            Item.identifier == raw_identifier,
            Item.item_type == item_type,
        )
    )
    result = await db.execute(query)
    exact = result.scalar_one_or_none()
    if exact:
        return exact, "exact"

    # 2. Normalized match: strip non-alphanumeric, lowercase
    normalized = _strip_to_alphanum(raw_identifier)
    # Load all items of this type and compare normalized identifiers
    all_items_result = await db.execute(
        select(Item).where(Item.item_type == item_type)
    )
    all_items = all_items_result.scalars().all()

    for item in all_items:
        if item.identifier and _strip_to_alphanum(item.identifier) == normalized:
            return item, "normalized"

    return None, "none"


# ─── Change Detection Helpers ─────────────────────────────────

async def _find_prior_context(
    db: AsyncSession,
    source_item_id: uuid.UUID,
    current_context: Item,
    all_context_items: dict[uuid.UUID, Item],
) -> Item | None:
    """
    Find the most recent prior context where this source has snapshots.

    Returns the milestone with the highest ordinal that is LESS THAN
    the current context's ordinal, or None if there is no prior context.

    Args:
        db: Database session
        source_item_id: The source item making assertions
        current_context: The current milestone context
        all_context_items: Dictionary mapping context IDs to Item objects
                          (for ordinal lookup)

    Returns:
        The prior milestone Item, or None if this is the first import
    """
    # Get current context's ordinal
    current_ordinal = current_context.properties.get("ordinal")
    if current_ordinal is None:
        return None

    try:
        current_ordinal = int(current_ordinal)
    except (ValueError, TypeError):
        return None

    # Get all milestones where this source has snapshots
    result = await db.execute(
        select(Snapshot.context_id).where(
            Snapshot.source_id == source_item_id
        ).distinct()
    )
    context_ids = result.scalars().all()

    # Load all context items
    contexts_result = await db.execute(
        select(Item).where(Item.id.in_(context_ids))
    )
    contexts = contexts_result.scalars().all()

    # Filter to milestones with ordinal < current, find max
    valid_contexts = []
    for ctx in contexts:
        ctx_ordinal = ctx.properties.get("ordinal")
        if ctx_ordinal is None:
            continue
        try:
            ctx_ordinal = int(ctx_ordinal)
        except (ValueError, TypeError):
            continue

        if ctx_ordinal < current_ordinal:
            valid_contexts.append((ctx_ordinal, ctx))

    if not valid_contexts:
        return None

    # Return context with highest ordinal
    valid_contexts.sort(key=lambda x: x[0], reverse=True)
    return valid_contexts[0][1]


# ─── Conflict Detection Helpers ───────────────────────────────

async def _get_or_create_conflict(
    db: AsyncSession,
    affected_item: Item,
    property_path: str,
) -> tuple[Item, bool]:
    """
    Get or create a conflict item for (affected_item, property).

    Per Decision 5: one conflict per property per item.
    Returns (conflict_item, is_new).
    """
    identifier = f"{affected_item.identifier} / {property_path}"

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
        },
    )
    db.add(conflict)
    await db.flush()
    await db.refresh(conflict)
    return conflict, True


async def _get_effective_snapshots_from_other_sources(
    db: AsyncSession,
    item_id: uuid.UUID,
    current_source_id: uuid.UUID,
    context_ordinal: int,
) -> dict[uuid.UUID, Snapshot]:
    """
    Get the effective snapshot from each OTHER source for an item.

    For each source (excluding the current importing source and workflow types),
    find the most recent snapshot at or before the context ordinal.
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

    workflow_types = {"change", "conflict", "decision", "note"}

    # Group by source, filter to other document sources
    effective: dict[uuid.UUID, Snapshot] = {}
    for snap in all_snaps:
        # Skip current source
        if snap.source_id == current_source_id:
            continue
        # Skip workflow types
        src = sources.get(snap.source_id)
        if not src or src.item_type in workflow_types:
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


# ─── Core Import Logic ────────────────────────────────────────

async def run_import(
    db: AsyncSession,
    file_bytes: bytes,
    source_item: Item,
    time_context: Item,
    mapping: ImportMappingConfig,
    project_id: uuid.UUID | None = None,
) -> ImportResult:
    """
    Execute the import pipeline.

    Steps:
      1. Parse file
      2. Match/create items
      3. Create snapshots (upsert on triple)
      4. Ensure connections
      5. Source self-snapshot
      6. Change detection (compare against prior source snapshots)
      7. Conflict detection (compare against other sources' effective values)
      8. Create import_batch item

    Returns ImportResult with summary, unmatched rows, change items, and conflict items.
    """
    # Parse the file
    if mapping.file_type == "csv":
        parsed_rows = parse_csv(file_bytes, mapping)
    else:
        parsed_rows = parse_excel(file_bytes, mapping)

    summary = ImportSummary()
    unmatched_rows: list[UnmatchedRow] = []
    change_items_result: list[ChangeItemResult] = []
    conflict_items_result: list[ConflictItemResult] = []

    # Create import batch item
    batch_item = Item(
        item_type="import_batch",
        identifier=f"Import-{source_item.identifier or 'unknown'}-{time_context.identifier or 'unknown'}",
        properties={
            "filename": mapping.file_type,
            "row_count": len(parsed_rows),
            "status": "processing",
            "source_item_id": str(source_item.id),
            "time_context_id": str(time_context.id),
        },
    )
    db.add(batch_item)
    await db.flush()
    await db.refresh(batch_item)

    # Step 1: Process each parsed row and store mapping of raw_id → matched_item
    row_to_item: dict[str, Item] = {}
    for row in parsed_rows:
        raw_id = row["_identifier"]
        row_num = row["_row_number"]

        # Extract properties (everything except _identifier and _row_number)
        props = {k: v for k, v in row.items() if not k.startswith("_")}

        # Match to existing item
        matched_item, confidence = await match_item(
            db, raw_id, mapping.target_item_type, project_id
        )

        if matched_item is None:
            # Unmatched: create new item
            matched_item = Item(
                item_type=mapping.target_item_type,
                identifier=raw_id,
                properties={},
            )
            db.add(matched_item)
            await db.flush()
            await db.refresh(matched_item)
            summary.items_created += 1
        elif confidence == "exact":
            summary.items_matched_exact += 1
        elif confidence == "normalized":
            summary.items_matched_normalized += 1

        summary.items_imported += 1

        # Store mapping for change detection
        row_to_item[raw_id] = matched_item

        # Upsert snapshot: (what=item, when=milestone, who=source)
        existing_snap_result = await db.execute(
            select(Snapshot).where(
                and_(
                    Snapshot.item_id == matched_item.id,
                    Snapshot.context_id == time_context.id,
                    Snapshot.source_id == source_item.id,
                )
            )
        )
        existing_snap = existing_snap_result.scalar_one_or_none()

        if existing_snap:
            existing_snap.properties = props
            await db.flush()
            summary.snapshots_upserted += 1
        else:
            snap = Snapshot(
                item_id=matched_item.id,
                context_id=time_context.id,
                source_id=source_item.id,
                properties=props,
            )
            db.add(snap)
            await db.flush()
            summary.snapshots_created += 1

        # Ensure connection: source → target
        existing_conn_result = await db.execute(
            select(Connection).where(
                and_(
                    Connection.source_item_id == source_item.id,
                    Connection.target_item_id == matched_item.id,
                )
            )
        )
        if existing_conn_result.scalar_one_or_none():
            summary.connections_existing += 1
        else:
            conn = Connection(
                source_item_id=source_item.id,
                target_item_id=matched_item.id,
                properties={"created_by_import": str(batch_item.id)},
            )
            db.add(conn)
            await db.flush()
            summary.connections_created += 1

    # Source self-snapshot: (what=source, when=milestone, who=source)
    source_self_result = await db.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == source_item.id,
                Snapshot.context_id == time_context.id,
                Snapshot.source_id == source_item.id,
            )
        )
    )
    source_self = source_self_result.scalar_one_or_none()
    source_self_props = {
        "row_count": len(parsed_rows),
        "columns_mapped": list(mapping.property_mapping.values()),
        "import_date": batch_item.created_at.isoformat() if batch_item.created_at else None,
        "file_type": mapping.file_type,
        "batch_id": str(batch_item.id),
    }
    if source_self:
        source_self.properties = source_self_props
        await db.flush()
    else:
        db.add(Snapshot(
            item_id=source_item.id,
            context_id=time_context.id,
            source_id=source_item.id,
            properties=source_self_props,
        ))
        await db.flush()

    # Step 3: Change Detection
    # Find the most recent prior context where this source has snapshots
    prior_context = await _find_prior_context(db, source_item.id, time_context, {})
    if prior_context:
        # Track affected items for summary
        affected_items_set: set[uuid.UUID] = set()

        for row in parsed_rows:
            raw_id = row["_identifier"]
            matched_item = row_to_item.get(raw_id)
            if not matched_item:
                continue

            # Get prior snapshot: (item, prior_context, source)
            prior_snap_result = await db.execute(
                select(Snapshot).where(
                    and_(
                        Snapshot.item_id == matched_item.id,
                        Snapshot.context_id == prior_context.id,
                        Snapshot.source_id == source_item.id,
                    )
                )
            )
            prior_snap = prior_snap_result.scalar_one_or_none()

            if not prior_snap:
                # No prior snapshot, so no changes to detect
                continue

            # Extract properties from row (current values)
            current_props = {k: v for k, v in row.items() if not k.startswith("_")}
            prior_props = prior_snap.properties

            # Compare properties using values_match
            changes: dict[str, dict[str, str | None]] = {}
            for prop_name, current_value in current_props.items():
                prior_value = prior_props.get(prop_name)
                if not values_match(prior_value, current_value, prop_name):
                    changes[prop_name] = {
                        "old": prior_value,
                        "new": current_value,
                    }

            # Create a change item for this (source, affected_item) with all property changes
            if changes:
                change_item = Item(
                    item_type="change",
                    identifier=f"{source_item.identifier} / {matched_item.identifier} / {prior_context.identifier}→{time_context.identifier}",
                    properties={
                        "status": "DETECTED",
                        "changes": changes,
                        "from_context": str(prior_context.id),
                        "to_context": str(time_context.id),
                        "source": str(source_item.id),
                        "affected_item": str(matched_item.id),
                    },
                )
                db.add(change_item)
                await db.flush()
                await db.refresh(change_item)

                # Create self-sourced snapshot: (what=change, when=context, who=change)
                change_snap = Snapshot(
                    item_id=change_item.id,
                    context_id=time_context.id,
                    source_id=change_item.id,  # Self-sourced
                    properties={
                        "status": "DETECTED",
                        "changes": changes,
                        "from_context": str(prior_context.id),
                        "to_context": str(time_context.id),
                        "source": str(source_item.id),
                        "affected_item": str(matched_item.id),
                    },
                )
                db.add(change_snap)
                await db.flush()

                # Create connections: change→source, change→to_context, change→from_context, change→affected_item
                conns = [
                    Connection(
                        source_item_id=change_item.id,
                        target_item_id=source_item.id,
                        properties={},
                    ),
                    Connection(
                        source_item_id=change_item.id,
                        target_item_id=time_context.id,
                        properties={"relationship": "to_context"},
                    ),
                    Connection(
                        source_item_id=change_item.id,
                        target_item_id=prior_context.id,
                        properties={"relationship": "from_context"},
                    ),
                    Connection(
                        source_item_id=change_item.id,
                        target_item_id=matched_item.id,
                        properties={},
                    ),
                ]
                for conn in conns:
                    db.add(conn)
                await db.flush()

                summary.source_changes += len(changes)
                affected_items_set.add(matched_item.id)

                # Add change item result for each property change
                for prop_name, change_details in changes.items():
                    change_items_result.append(
                        ChangeItemResult(
                            change_item_id=change_item.id,
                            affected_item_id=matched_item.id,
                            affected_item_identifier=matched_item.identifier,
                            property_name=prop_name,
                            old_value=change_details["old"],
                            new_value=change_details["new"],
                            from_context_id=prior_context.id,
                            to_context_id=time_context.id,
                        )
                    )

        summary.affected_items = len(affected_items_set)

    # Step 4: Conflict Detection
    # For each imported item, compare this source's values against other sources'
    # effective values. Create conflict items where they disagree.
    context_ordinal = time_context.properties.get("ordinal", 0) if time_context.properties else 0
    try:
        context_ordinal = int(context_ordinal)
    except (ValueError, TypeError):
        context_ordinal = 0

    # Load source items for identifiers
    all_source_ids_in_snaps = set()
    for row in parsed_rows:
        raw_id = row["_identifier"]
        matched_item = row_to_item.get(raw_id)
        if matched_item:
            all_source_ids_in_snaps.add(source_item.id)

    for row in parsed_rows:
        raw_id = row["_identifier"]
        matched_item = row_to_item.get(raw_id)
        if not matched_item:
            continue

        current_props = {k: v for k, v in row.items() if not k.startswith("_")}

        # Get effective snapshots from other sources
        other_effective = await _get_effective_snapshots_from_other_sources(
            db, matched_item.id, source_item.id, context_ordinal
        )

        if not other_effective:
            continue

        # Load source items for identifier display
        other_source_ids = set(other_effective.keys())
        other_sources_result = await db.execute(
            select(Item).where(Item.id.in_(other_source_ids))
        )
        other_sources = {s.id: s for s in other_sources_result.scalars().all()}

        for other_source_id, other_snap in other_effective.items():
            other_source = other_sources.get(other_source_id)
            other_source_identifier = other_source.identifier if other_source else str(other_source_id)

            for prop_name, new_value in current_props.items():
                other_value = other_snap.properties.get(prop_name)

                if other_value is None:
                    continue  # Other source doesn't address this property

                if not values_match(str(new_value), str(other_value), property_name=prop_name):
                    # Disagreement — create or get conflict item
                    conflict_item, is_new = await _get_or_create_conflict(
                        db, matched_item, prop_name
                    )

                    # Upsert conflict snapshot: (what=conflict, when=milestone, who=conflict)
                    existing_conflict_snap = await db.execute(
                        select(Snapshot).where(
                            and_(
                                Snapshot.item_id == conflict_item.id,
                                Snapshot.context_id == time_context.id,
                                Snapshot.source_id == conflict_item.id,
                            )
                        )
                    )
                    existing_cs = existing_conflict_snap.scalar_one_or_none()
                    conflict_snap_props = {
                        "status": "DETECTED",
                        "property_path": prop_name,
                        "values": {
                            str(source_item.identifier or source_item.id): str(new_value),
                            str(other_source_identifier): str(other_value),
                        },
                        "affected_item": str(matched_item.id),
                    }
                    if existing_cs:
                        existing_cs.properties = conflict_snap_props
                        await db.flush()
                    else:
                        db.add(Snapshot(
                            item_id=conflict_item.id,
                            context_id=time_context.id,
                            source_id=conflict_item.id,
                            properties=conflict_snap_props,
                        ))
                        await db.flush()

                    # Ensure connections: conflict → affected_item, conflict → both sources, conflict → milestone
                    for target_id in [matched_item.id, source_item.id, other_source_id, time_context.id]:
                        existing_conn = await db.execute(
                            select(Connection).where(
                                and_(
                                    Connection.source_item_id == conflict_item.id,
                                    Connection.target_item_id == target_id,
                                )
                            )
                        )
                        if not existing_conn.scalar_one_or_none():
                            db.add(Connection(
                                source_item_id=conflict_item.id,
                                target_item_id=target_id,
                                properties={},
                            ))
                            await db.flush()

                    if is_new:
                        summary.new_conflicts += 1

                    conflict_items_result.append(ConflictItemResult(
                        conflict_item_id=conflict_item.id,
                        affected_item_id=matched_item.id,
                        affected_item_identifier=matched_item.identifier,
                        property_name=prop_name,
                        values={
                            str(source_item.identifier or source_item.id): str(new_value),
                            str(other_source_identifier): str(other_value),
                        },
                        context_id=time_context.id,
                    ))

                else:
                    # Agreement — check if this resolves an existing conflict
                    existing_conflict_result = await db.execute(
                        select(Item).where(
                            and_(
                                Item.item_type == "conflict",
                                Item.identifier == f"{matched_item.identifier} / {prop_name}",
                            )
                        )
                    )
                    existing_conflict = existing_conflict_result.scalar_one_or_none()
                    if existing_conflict:
                        # Check if it's currently DETECTED (not already resolved)
                        if existing_conflict.properties.get("status") == "detected":
                            # Auto-resolve: create resolution snapshot
                            resolution_snap_result = await db.execute(
                                select(Snapshot).where(
                                    and_(
                                        Snapshot.item_id == existing_conflict.id,
                                        Snapshot.context_id == time_context.id,
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
                                    context_id=time_context.id,
                                    source_id=existing_conflict.id,
                                    properties=resolution_props,
                                ))
                            # Update conflict status
                            existing_conflict.properties = {
                                **existing_conflict.properties,
                                "status": "resolved_by_agreement",
                            }
                            await db.flush()
                            summary.resolved_conflicts += 1

    # Update batch status
    batch_item.properties = {**batch_item.properties, "status": "completed"}
    await db.flush()
    await db.refresh(batch_item)

    return ImportResult(
        batch_id=batch_item.id,
        source_item_id=source_item.id,
        time_context_id=time_context.id,
        summary=summary,
        unmatched=unmatched_rows,
        change_items=change_items_result,
        conflict_items=conflict_items_result,
    )


async def confirm_match(
    db: AsyncSession,
    batch_id: uuid.UUID,
    raw_identifier: str,
    matched_item_id: uuid.UUID,
    source_item_id: uuid.UUID,
    time_context_id: uuid.UUID,
    properties: dict | None = None,
) -> ConfirmMatchResponse:
    """
    Confirm a fuzzy match for an unmatched row.

    Creates the snapshot and connection for the confirmed match.
    """
    # Verify the matched item exists
    item_result = await db.execute(select(Item).where(Item.id == matched_item_id))
    matched_item = item_result.scalar_one_or_none()
    if not matched_item:
        raise ValueError(f"Matched item not found: {matched_item_id}")

    # Create snapshot
    snapshot_created = False
    existing_snap = await db.execute(
        select(Snapshot).where(
            and_(
                Snapshot.item_id == matched_item_id,
                Snapshot.context_id == time_context_id,
                Snapshot.source_id == source_item_id,
            )
        )
    )
    if not existing_snap.scalar_one_or_none():
        db.add(Snapshot(
            item_id=matched_item_id,
            context_id=time_context_id,
            source_id=source_item_id,
            properties=properties or {},
        ))
        await db.flush()
        snapshot_created = True

    # Ensure connection
    connection_created = False
    existing_conn = await db.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id == source_item_id,
                Connection.target_item_id == matched_item_id,
            )
        )
    )
    if not existing_conn.scalar_one_or_none():
        db.add(Connection(
            source_item_id=source_item_id,
            target_item_id=matched_item_id,
            properties={},
        ))
        await db.flush()
        connection_created = True

    return ConfirmMatchResponse(
        raw_identifier=raw_identifier,
        matched_item_id=matched_item_id,
        snapshot_created=snapshot_created,
        connection_created=connection_created,
    )
