"""
Extraction Confirmation Service — WP-17.3.

Processes user confirmation, correction, and rejection of LLM extraction
results. Handles property promotion for unrecognized terms.

This is the bridge between WP-17 (extraction) and WP-18 (propagation).
Confirmed extractions are stored on the extraction_batch item for
WP-18 to read and propagate as snapshots.
"""

import logging
import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Item
from app.schemas.extraction import SectionConfirmation
from app.services.property_service import get_or_create_property_item

logger = logging.getLogger(__name__)


async def confirm_extractions(
    db: AsyncSession,
    batch_id: uuid.UUID,
    confirmations: list[SectionConfirmation],
) -> dict[str, int]:
    """
    Process user confirmation of extraction results.

    For each section, processes:
      - Confirmed extractions: stored as-is in confirmed_extractions
      - Corrected extractions: stored with corrected value
      - Rejected extractions: excluded from confirmed_extractions
      - Promoted unrecognized terms: new PropertyDef + property item created

    Args:
        db: Async database session.
        batch_id: UUID of the extraction_batch item.
        confirmations: List of per-section user decisions.

    Returns:
        Dict with counts: confirmed, corrected, rejected, promoted.

    Raises:
        ValueError: If batch not found, not in extractable state, or
                    already confirmed.
    """
    # Load extraction batch
    result = await db.execute(
        select(Item).where(
            and_(
                Item.id == batch_id,
                Item.item_type == "extraction_batch",
            )
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Extraction batch {batch_id} not found")

    props = batch.properties or {}
    status = props.get("status")

    if status == "confirmed":
        raise ValueError(f"Extraction batch {batch_id} already confirmed")

    if status not in ("extracted", "partial"):
        raise ValueError(
            f"Extraction batch {batch_id} is not ready for confirmation "
            f"(status: {status})"
        )

    extraction_results = props.get("extraction_results", {})
    sections_data = extraction_results.get("sections", {})

    counts = {"confirmed": 0, "corrected": 0, "rejected": 0, "promoted": 0}

    # Build confirmation lookup
    confirmation_map = {c.section_number: c for c in confirmations}

    for section_num, section_data in sections_data.items():
        if section_data.get("status") == "failed":
            continue  # Skip failed sections

        section_conf = confirmation_map.get(section_num)
        if not section_conf:
            # No explicit decisions — auto-confirm all extractions
            confirmed_list = section_data.get("extractions", [])
            for ext in confirmed_list:
                ext["action"] = "confirm"
            section_data["confirmed_extractions"] = confirmed_list
            counts["confirmed"] += len(confirmed_list)
            section_data["status"] = "confirmed"
            continue

        # Process extraction decisions
        decision_map = {
            (d.property, d.element_type): d for d in section_conf.extraction_decisions
        }

        confirmed_extractions = []
        for ext in section_data.get("extractions", []):
            prop = ext.get("property", "")
            etype = ext.get("element_type", "")
            decision = decision_map.get((prop, etype))

            if not decision:
                # No explicit decision — default to confirm
                ext["action"] = "confirm"
                confirmed_extractions.append(ext)
                counts["confirmed"] += 1
                continue

            if decision.action == "confirm":
                ext["action"] = "confirm"
                confirmed_extractions.append(ext)
                counts["confirmed"] += 1

            elif decision.action == "correct":
                ext["action"] = "correct"
                ext["original_value"] = ext.get("value")
                ext["value"] = decision.corrected_value
                confirmed_extractions.append(ext)
                counts["corrected"] += 1

            elif decision.action == "reject":
                counts["rejected"] += 1
                # Not added to confirmed_extractions

        section_data["confirmed_extractions"] = confirmed_extractions

        # Process unrecognized term decisions
        unrec_decision_map = {d.term: d for d in section_conf.unrecognized_decisions}

        promoted_properties = []
        skipped_unrecognized = []

        for unrec in section_data.get("unrecognized", []):
            term = unrec.get("term", "")
            decision = unrec_decision_map.get(term)

            if not decision or decision.action == "skip":
                skipped_unrecognized.append(term)
                continue

            if decision.action == "add_as_property":
                prop_name = decision.property_name or term.lower().replace(" ", "_")
                target_types = decision.target_types or []
                data_type = decision.data_type or "string"

                # Create property items for each target type
                for target_type in target_types:
                    prop_item, is_new = await get_or_create_property_item(
                        db=db,
                        parent_type=target_type,
                        property_name=prop_name,
                    )

                    # If new, update its metadata with user-provided info
                    if is_new:
                        item_props = dict(prop_item.properties)
                        item_props["data_type"] = data_type
                        item_props["label"] = term  # Use original term as label
                        prop_item.properties = item_props

                promoted_properties.append(
                    {
                        "term": term,
                        "property_name": prop_name,
                        "target_types": target_types,
                        "data_type": data_type,
                        "value": unrec.get("value"),
                        "source_text": unrec.get("source_text"),
                    }
                )

                # Add the promoted property to confirmed extractions
                for target_type in target_types:
                    confirmed_extractions.append(
                        {
                            "property": prop_name,
                            "element_type": target_type,
                            "assertion_type": "flat",
                            "value": unrec.get("value", ""),
                            "confidence": 0.80,  # User-confirmed discovery
                            "source_text": unrec.get("source_text", ""),
                            "action": "promoted",
                        }
                    )

                counts["promoted"] += 1

        section_data["promoted_properties"] = promoted_properties
        section_data["skipped_unrecognized"] = skipped_unrecognized
        section_data["confirmed_extractions"] = confirmed_extractions
        section_data["status"] = "confirmed"

    # Update batch
    updated_props = dict(batch.properties)
    updated_props["status"] = "confirmed"
    updated_props["extraction_results"] = extraction_results
    batch.properties = updated_props

    await db.flush()

    return counts
