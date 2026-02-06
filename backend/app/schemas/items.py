"""Pydantic schemas for Items."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    """Schema for creating an item."""
    item_type: str = Field(..., description="Type key from type configuration")
    identifier: str | None = Field(None, description="Human-readable identifier")
    properties: dict = Field(default_factory=dict, description="Type-specific properties")


class ItemUpdate(BaseModel):
    """Schema for updating an item. Properties use merge semantics."""
    identifier: str | None = None
    properties: dict | None = None


class ItemResponse(BaseModel):
    """Schema for item in API responses."""
    id: uuid.UUID
    item_type: str
    identifier: str | None
    properties: dict
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ItemSummary(BaseModel):
    """Compact item representation for listings and connections."""
    id: uuid.UUID
    item_type: str
    identifier: str | None
    action_counts: dict = Field(default_factory=lambda: {"changes": 0, "conflicts": 0})

    model_config = {"from_attributes": True}


class PaginatedItems(BaseModel):
    """Paginated list of items with total count."""
    items: list[ItemResponse]
    total: int
    limit: int
    offset: int


# ─── Connected Items (Navigation) ─────────────────────────────

class ConnectedGroup(BaseModel):
    """A group of connected items sharing the same type."""
    item_type: str
    label: str
    items: list[ItemSummary]
    count: int


class ConnectedItemsResponse(BaseModel):
    """An item with its connected items grouped by type."""
    item: ItemResponse
    connected: list[ConnectedGroup]
