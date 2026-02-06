"""Pydantic schemas for Connections."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.items import ItemSummary


class ConnectionCreate(BaseModel):
    """Schema for creating a connection."""
    source_item_id: uuid.UUID = Field(..., description="The item this connection originates from")
    target_item_id: uuid.UUID = Field(..., description="The item this connection points to")
    properties: dict = Field(default_factory=dict, description="Connection metadata")

    @model_validator(mode="after")
    def prevent_self_connection(self):
        if self.source_item_id == self.target_item_id:
            raise ValueError("An item cannot be connected to itself")
        return self


class DisconnectRequest(BaseModel):
    """Schema for soft-disconnecting two items."""
    source_item_id: uuid.UUID
    target_item_id: uuid.UUID
    reason: str | None = Field(None, description="Why the disconnect happened")


class ConnectionResponse(BaseModel):
    """Schema for connection in API responses."""
    id: uuid.UUID
    source_item_id: uuid.UUID
    target_item_id: uuid.UUID
    properties: dict
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectionDetail(BaseModel):
    """Connection with expanded item info for navigation."""
    id: uuid.UUID
    source_item: ItemSummary
    target_item: ItemSummary
    properties: dict
    created_at: datetime

    model_config = {"from_attributes": True}
