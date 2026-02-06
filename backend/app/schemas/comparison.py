"""Pydantic schemas for temporal comparison — WP-8."""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.items import ItemSummary


class PropertyChange(BaseModel):
    """A property change between two milestones."""
    property_name: str = Field(..., description="Name of the property that changed")
    old_value: Any = Field(..., description="Value at the earlier milestone")
    new_value: Any = Field(..., description="Value at the later milestone")
    from_context: uuid.UUID = Field(..., description="Earlier milestone ID")
    to_context: uuid.UUID = Field(..., description="Later milestone ID")
    source: uuid.UUID | None = Field(None, description="Source that reported this change (None if merged)")

    model_config = {"from_attributes": True}


class ItemComparison(BaseModel):
    """Comparison of an item across two milestones."""
    item_id: uuid.UUID = Field(..., description="The item being compared")
    identifier: str | None = Field(None, description="Human-readable identifier")
    item_type: str = Field(..., description="Type of the item")
    category: str = Field(
        ...,
        description="Category: 'added', 'removed', 'modified', or 'unchanged'",
    )
    changes: list[PropertyChange] = Field(
        default_factory=list,
        description="Property-level changes (empty if unchanged or removed/added)",
    )

    model_config = {"from_attributes": True}


class ComparisonSummary(BaseModel):
    """Summary counts from a comparison."""
    added: int = Field(..., description="Number of items added")
    removed: int = Field(..., description="Number of items removed")
    modified: int = Field(..., description="Number of items modified")
    unchanged: int = Field(..., description="Number of items unchanged")
    total: int = Field(..., description="Total items compared")

    model_config = {"from_attributes": True}


class ComparisonRequest(BaseModel):
    """Request payload for comparing snapshots across milestones."""
    item_ids: list[uuid.UUID] | None = Field(
        None,
        description="Specific items to compare (mutually exclusive with parent_item_id)",
    )
    parent_item_id: uuid.UUID | None = Field(
        None,
        description="Parent item; compare all connected children (mutually exclusive with item_ids)",
    )
    from_context_id: uuid.UUID = Field(
        ...,
        description="Earlier milestone context ID",
    )
    to_context_id: uuid.UUID = Field(
        ...,
        description="Later milestone context ID",
    )
    source_filter: uuid.UUID | None = Field(
        None,
        description="Optional: if provided, only compare snapshots from this source",
    )
    limit: int = Field(100, ge=1, le=1000, description="Maximum items per page")
    offset: int = Field(0, ge=0, description="Pagination offset")

    model_config = {"from_attributes": True}


class ComparisonResult(BaseModel):
    """Result of a temporal comparison."""
    from_context: ItemSummary = Field(..., description="Earlier milestone")
    to_context: ItemSummary = Field(..., description="Later milestone")
    items: list[ItemComparison] = Field(
        ...,
        description="Paginated list of compared items",
    )
    summary: ComparisonSummary = Field(..., description="Summary counts")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")

    model_config = {"from_attributes": True}
