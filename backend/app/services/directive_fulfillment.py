"""
Shared directive fulfillment logic — WP-18.0.

Extracted from import_service.py to support both schedule import
and spec propagation pipelines.

Core function:
  - check_directive_fulfillment: Check if pending directives are fulfilled
    by newly imported/propagated property values.

Reuses fulfill_directive() from resolution_service.py for the actual
status update — this module handles the matching logic only.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Item, Snapshot
from app.services.normalization import values_match


# ─── Result Types ────────────────────────────────────────────


@dataclass
class FulfillmentResult:
    """Result of a single directive fulfillment."""
    directive_item: Item
    property_name: str
    target_value: str | None
    matched_value: str


@dataclass
class FulfillmentSummary:
    """Aggregate results from a batch fulfillment check."""
    directives_fulfilled: int = 0
    results: list[FulfillmentResult] = field(default_factory=list)


# ─── Core Functions ──────────────────────────────────────────


async def check_directive_fulfillment(
    db: AsyncSession,
    source_id: uuid.UUID,
    item_id: uuid.UUID,
    properties: dict[str, str],
) -> int:
    """
    Check if any pending directives targeting this source+item
    are fulfilled by the given property values.

    A directive is fulfilled when:
      - directive.status == "pending"
      - directive.target_source_id == str(source_id)
      - directive.affected_item_id == str(item_id)
      - values_match(imported_value, target_value, property_name) is True

    Args:
        db: Database session
        source_id: The source that just provided new values
        item_id: The item that received new values
        properties: Dict of property_name → value from the new assertion

    Returns:
        Count of directives fulfilled.
    """
    # Load all directives (Python-side filtering for SQLite compat)
    directive_result = await db.execute(
        select(Item).where(Item.item_type == "directive")
    )
    all_directives = directive_result.scalars().all()

    fulfilled_count = 0

    for directive in all_directives:
        if directive.properties.get("status") != "pending":
            continue
        if directive.properties.get("target_source_id") != str(source_id):
            continue

        affected_item_id = directive.properties.get("affected_item_id")
        if affected_item_id != str(item_id):
            continue

        target_value = directive.properties.get("target_value")
        prop_name = directive.properties.get("property_name")

        if not prop_name:
            continue

        imported_value = properties.get(prop_name)
        if imported_value is not None and target_value is not None:
            if values_match(str(imported_value), str(target_value), prop_name):
                # Fulfill the directive
                directive.properties = {**directive.properties, "status": "fulfilled"}

                # Also update the directive's self-sourced snapshot
                dir_snap_result = await db.execute(
                    select(Snapshot).where(
                        and_(
                            Snapshot.item_id == directive.id,
                            Snapshot.source_id == directive.id,
                        )
                    )
                )
                dir_snap = dir_snap_result.scalar_one_or_none()
                if dir_snap:
                    dir_snap.properties = {**dir_snap.properties, "status": "fulfilled"}
                await db.flush()
                fulfilled_count += 1

    return fulfilled_count


async def check_directive_fulfillment_batch(
    db: AsyncSession,
    items_with_values: list[tuple[uuid.UUID, uuid.UUID, dict[str, str]]],
) -> FulfillmentSummary:
    """
    Check directive fulfillment for a batch of items.

    Used by both import_service (schedule import) and propagation_service
    (spec propagation).

    Args:
        items_with_values: List of (source_id, item_id, properties)
            - source_id: The source that just provided new values
            - item_id: The item that received new values
            - properties: Dict of property_name → value

    Returns:
        FulfillmentSummary with aggregate counts.
    """
    summary = FulfillmentSummary()

    for source_id, item_id, properties in items_with_values:
        count = await check_directive_fulfillment(
            db, source_id, item_id, properties
        )
        summary.directives_fulfilled += count

    return summary
