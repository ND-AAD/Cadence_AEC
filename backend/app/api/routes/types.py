"""Type definition API routes (WP-DYN-2).

For alpha: firm resolved implicitly from authenticated user.
No firm ID in URLs -- just /v1/types.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.type_config import TypeConfig
from app.api.deps import get_current_user
from app.models.infrastructure import User
from app.services.dynamic_types import (
    resolve_user_firm,
    create_type_definition,
    get_merged_registry,
    update_type_definition,
    delete_type_definition,
    seed_firm_types,
)
from app.schemas.types import (
    TypeDefinitionCreate,
    TypeDefinitionUpdate,
    SeedResponse,
)

router = APIRouter()


def _tc_to_response(tc: TypeConfig) -> dict:
    """Convert TypeConfig to API response dict."""
    return {
        "name": tc.name,
        "label": tc.label,
        "plural_label": tc.plural_label,
        "category": tc.category,
        "navigable": tc.navigable,
        "is_source_type": tc.is_source_type,
        "is_context_type": tc.is_context_type,
        "render_mode": tc.render_mode,
        "exclude_from_conflicts": tc.exclude_from_conflicts,
        "search_fields": tc.search_fields,
        "valid_targets": tc.valid_targets,
        "default_sort": tc.default_sort,
        "properties": [
            {
                "name": p.name,
                "label": p.label,
                "data_type": p.data_type,
                "required": p.required,
                "unit": p.unit,
                "aliases": list(p.aliases) if p.aliases else None,
                "normalization": p.normalization,
                "enum_values": p.enum_values,
            }
            for p in tc.properties
        ],
    }


@router.post("/seed")
async def seed_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seed the user's firm with starter vocabulary."""
    firm = await resolve_user_firm(db, current_user.id)
    seeded = await seed_firm_types(db, firm.id)
    return SeedResponse(
        seeded_count=len(seeded),
        types=[tc.name for tc in seeded],
    )


@router.post("", status_code=201)
async def create_type(
    payload: TypeDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new type definition."""
    firm = await resolve_user_firm(db, current_user.id)
    try:
        tc = await create_type_definition(
            db,
            firm.id,
            type_name=payload.type_name,
            label=payload.label,
            plural_label=payload.plural_label,
            category=payload.category,
            render_mode=payload.render_mode,
            search_fields=payload.search_fields,
            property_defs=[pd.model_dump() for pd in payload.property_defs],
        )
    except ValueError as e:
        msg = str(e)
        if "OS type" in msg or "already exists" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return _tc_to_response(tc)


@router.get("")
async def list_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all types (OS + firm, merged)."""
    firm = await resolve_user_firm(db, current_user.id)
    merged = await get_merged_registry(db, firm.id)
    return {name: _tc_to_response(tc) for name, tc in merged.items()}


@router.get("/{type_name}")
async def get_type(
    type_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single type config."""
    firm = await resolve_user_firm(db, current_user.id)
    merged = await get_merged_registry(db, firm.id)
    if type_name not in merged:
        raise HTTPException(status_code=404, detail=f"Type '{type_name}' not found")
    return _tc_to_response(merged[type_name])


@router.patch("/{type_name}")
async def update_type(
    type_name: str,
    payload: TypeDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a type definition."""
    firm = await resolve_user_firm(db, current_user.id)
    try:
        kwargs = payload.model_dump(exclude_unset=True)
        if "property_defs" in kwargs and kwargs["property_defs"] is not None:
            kwargs["property_defs"] = [
                pd if isinstance(pd, dict) else pd.model_dump()
                for pd in kwargs["property_defs"]
            ]
        tc = await update_type_definition(db, firm.id, type_name, **kwargs)
    except ValueError as e:
        msg = str(e)
        if "OS type" in msg:
            raise HTTPException(status_code=403, detail=msg)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return _tc_to_response(tc)


@router.delete("/{type_name}", status_code=204)
async def delete_type(
    type_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a type definition."""
    firm = await resolve_user_firm(db, current_user.id)
    try:
        await delete_type_definition(db, firm.id, type_name)
    except ValueError as e:
        msg = str(e)
        if "OS type" in msg:
            raise HTTPException(status_code=403, detail=msg)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        if "items exist" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
