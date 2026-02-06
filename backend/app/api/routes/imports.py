"""
Import API routes — WP-6: Import pipeline.

Endpoints:
  POST   /api/v1/import              — Import a file (Excel/CSV)
  GET    /api/v1/import/:batch_id    — Get import batch status
  GET    /api/v1/import/:batch_id/unmatched — Get unmatched rows
  POST   /api/v1/import/:batch_id/confirm-match — Confirm a fuzzy match

  GET    /api/v1/items/:source_id/import-mapping — Get stored mapping
  PUT    /api/v1/items/:source_id/import-mapping — Store/update mapping

Single-writer enforcement: one import per project at a time.
"""

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.type_config import get_type_config
from app.models.core import Connection, Item, Snapshot
from app.schemas.imports import (
    ConfirmMatchRequest,
    ConfirmMatchResponse,
    ImportMappingConfig,
    ImportResult,
    UnmatchedRow,
)
from app.services.import_service import confirm_match, run_import

router = APIRouter()


# ─── Helpers ───────────────────────────────────────────────────

async def _get_item_or_404(
    db: AsyncSession, item_id: uuid.UUID, label: str = "Item"
) -> Item:
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail=f"{label} not found: {item_id}")
    return item


async def _validate_context(db: AsyncSession, context_id: uuid.UUID) -> Item:
    context = await _get_item_or_404(db, context_id, "Context (milestone)")
    type_cfg = get_type_config(context.item_type)
    if not type_cfg or not type_cfg.is_context_type:
        raise HTTPException(
            status_code=400,
            detail=f"Context must be a milestone. Got type '{context.item_type}'.",
        )
    return context


# ─── Import Mapping CRUD ──────────────────────────────────────

@router.get(
    "/items/{source_id}/import-mapping",
    response_model=ImportMappingConfig | None,
)
async def get_import_mapping(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the import mapping stored on a source item.

    The mapping is stored in the source item's properties under the
    key 'import_mapping'.
    """
    source = await _get_item_or_404(db, source_id, "Source")
    mapping_data = source.properties.get("import_mapping")
    if not mapping_data:
        return None
    return ImportMappingConfig(**mapping_data)


@router.put(
    "/items/{source_id}/import-mapping",
    response_model=ImportMappingConfig,
)
async def set_import_mapping(
    source_id: uuid.UUID,
    mapping: ImportMappingConfig,
    db: AsyncSession = Depends(get_db),
):
    """
    Store or update the import mapping on a source item.

    The mapping is persisted in the source item's properties under
    'import_mapping', allowing reuse across imports.
    """
    source = await _get_item_or_404(db, source_id, "Source")

    # Validate the target item type exists in type config
    if not get_type_config(mapping.target_item_type):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown target item type: {mapping.target_item_type}",
        )

    # Store mapping in source properties (merge, don't replace)
    new_props = {**source.properties, "import_mapping": mapping.model_dump()}
    source.properties = new_props
    await db.flush()
    await db.refresh(source)
    return mapping


# ─── Main Import Endpoint ─────────────────────────────────────

@router.post("/import", response_model=ImportResult, status_code=201)
async def import_file(
    file: UploadFile = File(...),
    source_item_id: str = Form(...),
    time_context_id: str = Form(...),
    mapping_config: str | None = Form(None, description="JSON-encoded ImportMappingConfig"),
    db: AsyncSession = Depends(get_db),
):
    """
    Import a file (Excel/CSV) and create source-attributed snapshots.

    For each row in the file:
      1. Match to existing item by identifier (exact → normalized)
      2. Create new item if no match found
      3. Upsert snapshot: (what=item, when=milestone, who=source)
      4. Ensure connection: source → item

    Also creates:
      - Source self-snapshot with import metadata
      - Import batch item to track this import

    If mapping_config is omitted, uses the mapping stored on the source item.
    """
    # Parse UUIDs
    try:
        src_id = uuid.UUID(source_item_id)
        ctx_id = uuid.UUID(time_context_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {e}")

    # Validate source and context
    source_item = await _get_item_or_404(db, src_id, "Source item")
    time_context = await _validate_context(db, ctx_id)

    # Resolve mapping configuration
    mapping: ImportMappingConfig | None = None
    if mapping_config:
        try:
            mapping = ImportMappingConfig(**json.loads(mapping_config))
        except (json.JSONDecodeError, Exception) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mapping_config JSON: {e}",
            )
    else:
        # Try stored mapping on source item
        stored = source_item.properties.get("import_mapping")
        if stored:
            mapping = ImportMappingConfig(**stored)

    if not mapping:
        raise HTTPException(
            status_code=400,
            detail="No mapping configuration provided and none stored on source item. "
                   "Provide mapping_config or PUT a mapping to "
                   f"/api/v1/items/{source_item_id}/import-mapping first.",
        )

    # Read file bytes
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Store/update mapping on source item for reuse
    source_item.properties = {
        **source_item.properties,
        "import_mapping": mapping.model_dump(),
    }
    await db.flush()

    # Determine project_id from source item connections (optional)
    project_id = None

    # Run the import
    result = await run_import(
        db=db,
        file_bytes=file_bytes,
        source_item=source_item,
        time_context=time_context,
        mapping=mapping,
        project_id=project_id,
    )

    return result


# ─── Batch Status ─────────────────────────────────────────────

@router.get("/import/{batch_id}", response_model=dict)
async def get_import_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the status and metadata of an import batch."""
    batch = await _get_item_or_404(db, batch_id, "Import batch")
    if batch.item_type != "import_batch":
        raise HTTPException(
            status_code=400,
            detail=f"Item {batch_id} is not an import batch (type: {batch.item_type})",
        )
    return {
        "id": batch.id,
        "identifier": batch.identifier,
        "properties": batch.properties,
        "created_at": batch.created_at,
    }


# ─── Unmatched / Confirm ──────────────────────────────────────

@router.get("/import/{batch_id}/unmatched", response_model=list[UnmatchedRow])
async def get_unmatched(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get unmatched rows from an import batch that need user confirmation.

    Currently returns empty since WP-6 creates items for unmatched rows.
    Fuzzy match confirmation will be implemented when pg_trgm is available.
    """
    batch = await _get_item_or_404(db, batch_id, "Import batch")
    if batch.item_type != "import_batch":
        raise HTTPException(
            status_code=400,
            detail=f"Item {batch_id} is not an import batch",
        )
    # In the current implementation, unmatched rows get new items created.
    # Future: store unmatched rows on batch properties for fuzzy confirmation.
    return []


@router.post(
    "/import/{batch_id}/confirm-match",
    response_model=ConfirmMatchResponse,
)
async def confirm_import_match(
    batch_id: uuid.UUID,
    payload: ConfirmMatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm a fuzzy match for an unmatched import row.

    Creates the snapshot and connection for the confirmed match.
    """
    batch = await _get_item_or_404(db, batch_id, "Import batch")
    if batch.item_type != "import_batch":
        raise HTTPException(
            status_code=400,
            detail=f"Item {batch_id} is not an import batch",
        )

    # Extract source and context from batch properties
    source_item_id = batch.properties.get("source_item_id")
    time_context_id = batch.properties.get("time_context_id")
    if not source_item_id or not time_context_id:
        raise HTTPException(
            status_code=400,
            detail="Batch is missing source_item_id or time_context_id in properties",
        )

    result = await confirm_match(
        db=db,
        batch_id=batch_id,
        raw_identifier=payload.raw_identifier,
        matched_item_id=payload.matched_item_id,
        source_item_id=uuid.UUID(source_item_id),
        time_context_id=uuid.UUID(time_context_id),
    )
    return result
