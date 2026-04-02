"""Pydantic schemas for type definition API (WP-DYN-2)."""

from pydantic import BaseModel, Field


class PropertyDefSchema(BaseModel):
    name: str
    label: str
    data_type: str = "string"
    required: bool = False
    unit: str | None = None
    aliases: list[str] | None = None
    normalization: str | None = None
    enum_values: list[str] | None = None


class TypeDefinitionCreate(BaseModel):
    type_name: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    plural_label: str | None = None
    category: str = "spatial"
    render_mode: str = "table"
    search_fields: list[str] = []
    property_defs: list[PropertyDefSchema] = []


class TypeDefinitionUpdate(BaseModel):
    label: str | None = None
    plural_label: str | None = None
    render_mode: str | None = None
    search_fields: list[str] | None = None
    property_defs: list[PropertyDefSchema] | None = None


class TypeConfigResponse(BaseModel):
    name: str
    label: str
    plural_label: str
    category: str
    navigable: bool
    is_source_type: bool
    is_context_type: bool
    render_mode: str
    exclude_from_conflicts: bool
    search_fields: list[str]
    valid_targets: list[str]
    default_sort: str
    properties: list[PropertyDefSchema]

    model_config = {"from_attributes": True}


class SeedResponse(BaseModel):
    seeded_count: int
    types: list[str]
