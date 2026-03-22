"""
Specification propagation service — WP-18.1.

Propagates confirmed extraction results to the live graph by creating
source-attributed snapshots and running conflict detection + directive
fulfillment.

This service is entirely deterministic — no LLM calls. Intelligence was
front-loaded into WP-17's extraction pipeline.

Pipeline:
  1. Read confirmed extraction batch
  2. Create section-level snapshots (section self-snapshot)
  3. Propagate to attributed elements (element-level snapshots)
  4. Handle conditional assertions (needs_assignment flag)
  5. Run conflict detection on propagated snapshots
  6. Run directive fulfillment check
  7. Create spec_section → element connections
  8. Update batch status to "propagated"
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Connection, Item, Snapshot
from app.services.conflict_detection import detect_conflicts_for_item
from app.services.directive_fulfillment import check_directive_fulfillment


# ─── Result Types ────────────────────────────────────────────


@dataclass
class PropagationResult:
    """Summary of a propagation run."""

    batch_id: uuid.UUID
    status: str = "propagated"
    section_snapshots_created: int = 0
    element_snapshots_created: int = 0
    element_snapshots_updated: int = 0
    conditionals_deferred: int = 0
    conflicts_detected: int = 0
    conflicts_auto_resolved: int = 0
    directives_fulfilled: int = 0
    discovered_entities: int = 0


# ─── Helpers ─────────────────────────────────────────────────


async def _ensure_connection(
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
        db.add(
            Connection(
                source_item_id=source_item_id,
                target_item_id=target_item_id,
                properties=properties or {},
            )
        )
        await db.flush()


def _is_conditional(value) -> bool:
    """Check if a value is a conditional assertion from WP-17."""
    if isinstance(value, dict):
        return (
            value.get("conditional") is True
            or value.get("assertion_type") == "conditional"
        )
    return False


def _transform_conditional_to_snapshot(value: dict) -> dict:
    """
    Transform WP-17's conditional extraction format into snapshot property format.

    WP-17 format:
        {"conditional": True, "assertions": [{"value": "B-Label", "condition": "..."}]}
    or:
        {"assertion_type": "conditional", "assertions": [...]}

    Snapshot format:
        {"_conditional": True, "_needs_assignment": True, "assertions": [...]}
    """
    assertions = value.get("assertions", [])
    return {
        "_conditional": True,
        "_needs_assignment": True,
        "assertions": assertions,
    }


def _extract_flat_properties(extractions: list[dict]) -> dict:
    """
    Build a properties dict from confirmed extractions.

    Flat assertions → concrete values.
    Conditional assertions → conditional structure with needs_assignment.

    Args:
        extractions: List of ExtractionItem dicts with property_name, value,
                     assertion_type, etc.

    Returns:
        Dict of property_name → value (str for flat, dict for conditional)
    """
    props: dict = {}
    for extraction in extractions:
        prop_name = extraction.get("property_name")
        if not prop_name:
            continue

        assertion_type = extraction.get("assertion_type", "flat")
        if assertion_type == "conditional":
            # Conditional: build deferred assignment structure
            assertions = extraction.get("assertions", [])
            props[prop_name] = {
                "_conditional": True,
                "_needs_assignment": True,
                "assertions": assertions,
            }
        else:
            # Flat assertion: concrete value
            value = extraction.get("value")
            if value is not None:
                props[prop_name] = str(value)

    return props


# ─── Core Function ───────────────────────────────────────────


async def propagate_extractions(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> PropagationResult:
    """
    Propagate confirmed extractions to section-level and element-level snapshots.

    Steps:
      1. Load confirmed extraction batch
      2. For each section: create section-level snapshot
      3. For each noun with attributed elements: create element-level snapshots
      4. Handle conditional assertions (Tier 2: propagate with needs_assignment)
      5. Run conflict detection on propagated snapshots
      6. Run directive fulfillment check
      7. Create spec_section → element connections
      8. Update batch status to "propagated"

    Args:
        db: Async database session.
        batch_id: UUID of the confirmed extraction_batch item.

    Returns:
        PropagationResult with snapshot counts, conflict counts, directive counts.

    Raises:
        ValueError: If batch not found, not confirmed, or already propagated.
    """
    result = PropagationResult(batch_id=batch_id)

    # ── Step 1: Load and validate batch ──────────────────────
    batch_result = await db.execute(
        select(Item).where(
            and_(
                Item.id == batch_id,
                Item.item_type == "extraction_batch",
            )
        )
    )
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Extraction batch not found: {batch_id}")

    batch_status = batch.properties.get("status", "")
    if batch_status == "propagated":
        raise ValueError(f"Batch already propagated: {batch_id}")
    if batch_status != "confirmed":
        raise ValueError(
            f"Batch must be in 'confirmed' status to propagate (current: {batch_status})"
        )

    # Load the milestone context from the batch
    milestone_id_str = batch.properties.get("milestone_id")
    if not milestone_id_str:
        raise ValueError("Batch missing milestone_id in properties")
    milestone_id = uuid.UUID(milestone_id_str)

    milestone_result = await db.execute(select(Item).where(Item.id == milestone_id))
    milestone = milestone_result.scalar_one_or_none()
    if not milestone:
        raise ValueError(f"Milestone not found: {milestone_id}")

    # Read extraction results
    extraction_results = batch.properties.get("extraction_results", {})
    sections = extraction_results.get("sections", {})

    # ── Step 2–7: Process each section ───────────────────────
    for section_number, section_data in sections.items():
        if section_data.get("status") != "extracted":
            continue

        # Find the spec_section item
        section_item_id_str = section_data.get("section_item_id")
        if not section_item_id_str:
            # Try to find by section number
            sec_result = await db.execute(
                select(Item).where(
                    and_(
                        Item.item_type == "spec_section",
                        Item.identifier == section_number,
                    )
                )
            )
            section_item = sec_result.scalar_one_or_none()
            if not section_item:
                continue
        else:
            sec_result = await db.execute(
                select(Item).where(Item.id == uuid.UUID(section_item_id_str))
            )
            section_item = sec_result.scalar_one_or_none()
            if not section_item:
                continue

        # Gather all flat values across all nouns for section-level snapshot
        section_all_props: dict = {}
        nouns = section_data.get("nouns", [])

        for noun_data in nouns:
            attribution_status = noun_data.get("attribution_status", "unmatched_type")
            extractions = noun_data.get("extractions", [])

            if not extractions:
                continue

            noun_props = _extract_flat_properties(extractions)

            # Count conditionals
            for prop_name, value in noun_props.items():
                if isinstance(value, dict) and value.get("_conditional"):
                    result.conditionals_deferred += 1

            # Aggregate into section-level properties
            section_all_props.update(noun_props)

            # ── Step 3: Element-level snapshots ──────────────
            attributed_elements = noun_data.get("attributed_elements", [])

            if attribution_status == "no_elements":
                result.discovered_entities += 1
                continue

            if not attributed_elements:
                continue

            matched_type = noun_data.get("matched_type")

            for element_id_str in attributed_elements:
                element_id = uuid.UUID(element_id_str)

                # Load element item
                elem_result = await db.execute(
                    select(Item).where(Item.id == element_id)
                )
                element = elem_result.scalar_one_or_none()
                if not element:
                    continue

                # Only apply properties matching the element's type
                if matched_type and element.item_type != matched_type:
                    continue

                # Build element-level properties (only flat values for conflict detection)
                element_props = {}
                flat_props_for_detection = {}
                for prop_name, value in noun_props.items():
                    element_props[prop_name] = value
                    if isinstance(value, str):
                        flat_props_for_detection[prop_name] = value

                # Upsert element-level snapshot:
                # (what=element, when=milestone, who=spec_section)
                existing_snap_result = await db.execute(
                    select(Snapshot).where(
                        and_(
                            Snapshot.item_id == element_id,
                            Snapshot.context_id == milestone.id,
                            Snapshot.source_id == section_item.id,
                        )
                    )
                )
                existing_snap = existing_snap_result.scalar_one_or_none()

                if existing_snap:
                    existing_snap.properties = element_props
                    await db.flush()
                    result.element_snapshots_updated += 1
                else:
                    db.add(
                        Snapshot(
                            item_id=element_id,
                            context_id=milestone.id,
                            source_id=section_item.id,  # D-21: section is the source
                            properties=element_props,
                        )
                    )
                    await db.flush()
                    result.element_snapshots_created += 1

                # ── Step 7: Connection: spec_section → element ───
                noun_phrase = noun_data.get("noun_phrase", "")
                await _ensure_connection(
                    db,
                    section_item.id,
                    element_id,
                    {"relationship": "spec_governs", "noun_phrase": noun_phrase},
                )

                # ── Step 5: Conflict detection ───────────────
                # Only run on flat (non-conditional) properties
                if flat_props_for_detection:
                    conflicts, auto_resolutions = await detect_conflicts_for_item(
                        db,
                        element,
                        section_item.id,
                        milestone,
                        flat_props_for_detection,
                    )
                    result.conflicts_detected += sum(1 for c in conflicts if c.is_new)
                    result.conflicts_auto_resolved += len(auto_resolutions)

                # ── Step 6: Directive fulfillment ────────────
                if flat_props_for_detection:
                    fulfilled = await check_directive_fulfillment(
                        db,
                        section_item.id,
                        element_id,
                        flat_props_for_detection,
                    )
                    result.directives_fulfilled += fulfilled

        # ── Step 2: Section-level snapshot ────────────────────
        # (what=section, when=milestone, who=section) — self-sourced
        if section_all_props:
            existing_sec_snap = await db.execute(
                select(Snapshot).where(
                    and_(
                        Snapshot.item_id == section_item.id,
                        Snapshot.context_id == milestone.id,
                        Snapshot.source_id == section_item.id,
                    )
                )
            )
            existing_ss = existing_sec_snap.scalar_one_or_none()
            if existing_ss:
                existing_ss.properties = section_all_props
                await db.flush()
            else:
                db.add(
                    Snapshot(
                        item_id=section_item.id,
                        context_id=milestone.id,
                        source_id=section_item.id,
                        properties=section_all_props,
                    )
                )
                await db.flush()
                result.section_snapshots_created += 1

    # ── Step 8: Update batch status ──────────────────────────
    batch.properties = {**batch.properties, "status": "propagated"}
    await db.flush()

    return result


# ─── Conditional Assignment ──────────────────────────────────


async def get_pending_assignments(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> list[dict]:
    """
    Get elements with conditional properties needing assignment.

    Returns list of dicts:
      {
        "element_id": uuid, "element_identifier": str,
        "property_name": str, "assertions": [...],
        "section_number": str, "section_item_id": uuid,
      }
    """
    batch_result = await db.execute(select(Item).where(Item.id == batch_id))
    batch = batch_result.scalar_one_or_none()
    if not batch:
        return []

    extraction_results = batch.properties.get("extraction_results", {})
    sections = extraction_results.get("sections", {})

    pending: list[dict] = []

    for section_number, section_data in sections.items():
        section_item_id_str = section_data.get("section_item_id")
        nouns = section_data.get("nouns", [])

        for noun_data in nouns:
            extractions = noun_data.get("extractions", [])
            attributed_elements = noun_data.get("attributed_elements", [])

            for extraction in extractions:
                if extraction.get("assertion_type") != "conditional":
                    continue

                prop_name = extraction.get("property_name")
                assertions = extraction.get("assertions", [])

                for element_id_str in attributed_elements:
                    # Load element
                    elem_result = await db.execute(
                        select(Item).where(Item.id == uuid.UUID(element_id_str))
                    )
                    element = elem_result.scalar_one_or_none()
                    if not element:
                        continue

                    # Check if still needs assignment
                    section_item_id = (
                        uuid.UUID(section_item_id_str) if section_item_id_str else None
                    )
                    if section_item_id:
                        snap_result = await db.execute(
                            select(Snapshot).where(
                                and_(
                                    Snapshot.item_id == element.id,
                                    Snapshot.source_id == section_item_id,
                                )
                            )
                        )
                        snap = snap_result.scalar_one_or_none()
                        if snap and snap.properties.get(prop_name):
                            prop_val = snap.properties[prop_name]
                            if isinstance(prop_val, dict) and prop_val.get(
                                "_needs_assignment"
                            ):
                                pending.append(
                                    {
                                        "element_id": element.id,
                                        "element_identifier": element.identifier,
                                        "property_name": prop_name,
                                        "assertions": assertions,
                                        "section_number": section_number,
                                        "section_item_id": section_item_id,
                                    }
                                )

    return pending


async def assign_conditional_values(
    db: AsyncSession,
    assignments: list[dict],
    batch_id: uuid.UUID,
) -> dict:
    """
    Resolve conditional assertions by assigning concrete values.

    Each assignment is:
      {
        "element_ids": [uuid, ...],
        "property_name": str,
        "value": str,
        "source_condition": str,
        "section_item_id": uuid,
      }

    After assignment:
      - Updates element snapshots: replace conditional with concrete value
      - Removes _needs_assignment flag
      - Runs conflict detection on newly concrete values

    Returns:
        {"assignments_made": int, "conflicts_detected": int}
    """
    assignments_made = 0
    conflicts_detected = 0

    # Load batch for milestone
    batch_result = await db.execute(select(Item).where(Item.id == batch_id))
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Batch not found: {batch_id}")

    milestone_id = uuid.UUID(batch.properties.get("milestone_id", ""))
    milestone_result = await db.execute(select(Item).where(Item.id == milestone_id))
    milestone = milestone_result.scalar_one_or_none()
    if not milestone:
        raise ValueError(f"Milestone not found: {milestone_id}")

    for assignment in assignments:
        element_ids = assignment.get("element_ids", [])
        prop_name = assignment.get("property_name")
        value = assignment.get("value")
        section_item_id = assignment.get("section_item_id")

        if not prop_name or value is None or not section_item_id:
            continue

        if isinstance(section_item_id, str):
            section_item_id = uuid.UUID(section_item_id)

        for element_id in element_ids:
            if isinstance(element_id, str):
                element_id = uuid.UUID(element_id)

            # Find the element's snapshot from this section
            snap_result = await db.execute(
                select(Snapshot).where(
                    and_(
                        Snapshot.item_id == element_id,
                        Snapshot.source_id == section_item_id,
                    )
                )
            )
            snap = snap_result.scalar_one_or_none()
            if not snap:
                continue

            # Replace conditional with concrete value
            updated_props = dict(snap.properties)
            updated_props[prop_name] = value
            snap.properties = updated_props
            await db.flush()
            assignments_made += 1

            # Run conflict detection on the now-concrete value
            elem_result = await db.execute(select(Item).where(Item.id == element_id))
            element = elem_result.scalar_one_or_none()
            if element:
                conflicts, _ = await detect_conflicts_for_item(
                    db,
                    element,
                    section_item_id,
                    milestone,
                    {prop_name: value},
                )
                conflicts_detected += sum(1 for c in conflicts if c.is_new)

    return {
        "assignments_made": assignments_made,
        "conflicts_detected": conflicts_detected,
    }
