"""
Import API routes — WP-6 + WP-6b.

Endpoints:
  POST   /api/v1/import                          — Import a file (Excel/CSV)
  GET    /api/v1/import/:batch_id                — Get import batch status
  GET    /api/v1/import/:batch_id/unmatched      — Get unmatched rows
  POST   /api/v1/import/:batch_id/confirm-match  — Confirm a fuzzy match

  GET    /api/v1/items/:source_id/import-mapping  — Get stored mapping
  PUT    /api/v1/items/:source_id/import-mapping  — Store/update mapping

  POST   /api/v1/import/analyze                   — WP-6b: Analyze file, propose mapping
  POST   /api/v1/import/analyze/:proposal_id/confirm — WP-6b: Confirm/correct mapping

Single-writer enforcement: one import per project at a time.
"""

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_access, get_project_for_item
from app.core.database import get_db
from app.core.type_config import get_type_config
from app.services.dynamic_types import resolve_user_firm, get_merged_registry
from app.models.core import Connection, Item
from app.models.infrastructure import User
from app.schemas.imports import (
    ColumnProposalResponse,
    ConfirmMatchRequest,
    ConfirmMatchResponse,
    ImportMappingConfig,
    ImportResult,
    MappingConfirmResponse,
    MappingCorrectionRequest,
    ProposedMappingResponse,
    UnmatchedRow,
)
from app.services.auto_mapping import propose_mapping
from app.services.import_service import confirm_match, run_import

router = APIRouter()

# In-memory proposal cache (per-process). Production would use Redis or DB.
_proposal_cache: dict[uuid.UUID, dict] = {}


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


async def _load_user_aliases(
    db: AsyncSession, project_id: uuid.UUID | None
) -> dict[str, str] | None:
    """Load user alias corrections from project properties."""
    if not project_id:
        return None
    result = await db.execute(select(Item).where(Item.id == project_id))
    project = result.scalar_one_or_none()
    if not project or not project.properties:
        return None
    return project.properties.get("column_alias_corrections")


# ─── Import Mapping CRUD ──────────────────────────────────────


@router.get(
    "/items/{source_id}/import-mapping",
    response_model=ImportMappingConfig | None,
)
async def get_import_mapping(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Store or update the import mapping on a source item.

    The mapping is persisted in the source item's properties under
    'import_mapping', allowing reuse across imports.
    """
    source = await _get_item_or_404(db, source_id, "Source")

    # Validate the target item type exists in OS config or firm vocabulary
    if not get_type_config(mapping.target_item_type):
        firm = await resolve_user_firm(db, current_user.id)
        merged = await get_merged_registry(db, firm.id)
        if mapping.target_item_type not in merged:
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


# ─── WP-6b: Auto-Mapping Endpoints ──────────────────────────────


@router.post(
    "/import/analyze",
    response_model=ProposedMappingResponse,
)
async def analyze_file(
    file: UploadFile = File(...),
    source_item_id: str | None = Form(None),
    project_id: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a file and propose column-to-property mapping (WP-6b).

    Accepts a file (multipart) and optional hints. Returns a
    ProposedMapping without executing the import.

    The user uploads a file, sees the proposed mapping, and either
    confirms or corrects before triggering the actual import.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Determine file type
    filename = file.filename or ""
    if filename.lower().endswith(".csv"):
        file_type = "csv"
    else:
        file_type = "excel"

    # Load user aliases from project if available
    proj_id = None
    user_aliases = None
    if project_id:
        try:
            proj_id = uuid.UUID(project_id)
            await require_project_access(db, proj_id, current_user)
            user_aliases = await _load_user_aliases(db, proj_id)
        except ValueError:
            pass

    # Run auto-mapping analysis
    proposed = propose_mapping(
        file_bytes=file_bytes,
        file_type=file_type,
        user_aliases=user_aliases,
        project_id=str(proj_id) if proj_id else None,
    )

    # Build response
    proposal_id = uuid.uuid4()
    column_responses = [
        ColumnProposalResponse(
            column_name=cp.column_name,
            proposed_property=cp.proposed_property,
            confidence=cp.confidence,
            match_method=cp.match_method,
            alternatives=cp.alternatives,
        )
        for cp in proposed.columns
    ]

    response = ProposedMappingResponse(
        proposal_id=proposal_id,
        header_row=proposed.header_row,
        header_row_confidence=proposed.header_row_confidence,
        target_item_type=proposed.target_item_type,
        type_confidence=proposed.type_confidence,
        identifier_column=proposed.identifier_column,
        identifier_confidence=proposed.identifier_confidence,
        columns=column_responses,
        unmatched_columns=proposed.unmatched_columns,
        proposed_config=proposed.proposed_config,
        overall_confidence=proposed.overall_confidence,
        needs_user_review=proposed.needs_user_review,
    )

    # Cache the proposal for the confirm endpoint
    _proposal_cache[proposal_id] = {
        "proposed": proposed,
        "file_bytes": file_bytes,
        "file_type": file_type,
        "source_item_id": source_item_id,
        "project_id": str(proj_id) if proj_id else None,
    }

    return response


@router.post(
    "/import/analyze/{proposal_id}/confirm",
    response_model=MappingConfirmResponse,
)
async def confirm_mapping(
    proposal_id: uuid.UUID,
    payload: MappingCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm or correct a proposed mapping (WP-6b).

    Accepts corrections to a ProposedMapping. Stores confirmed
    corrections in the project's alias registry. Returns the final
    ImportMappingConfig ready for import.
    """
    cached = _proposal_cache.get(proposal_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"Proposal {proposal_id} not found or expired.",
        )

    proposed = cached["proposed"]
    corrections = payload.corrections

    # Apply corrections to the proposed config
    config = proposed.proposed_config
    if not config:
        raise HTTPException(
            status_code=400,
            detail="Proposal has no base configuration to correct.",
        )

    # Override header row, identifier, or type if provided
    final_header_row = payload.header_row or config.header_row
    final_identifier = payload.identifier_column or config.identifier_column
    final_type = payload.target_item_type or config.target_item_type

    # Apply column corrections
    final_mapping = dict(config.property_mapping)
    for col_name, corrected_prop in corrections.items():
        if corrected_prop is None:
            # User wants to skip this column
            final_mapping.pop(col_name, None)
        else:
            final_mapping[col_name] = corrected_prop

    confirmed_config = ImportMappingConfig(
        file_type=config.file_type,
        identifier_column=final_identifier,
        target_item_type=final_type,
        header_row=final_header_row,
        property_mapping=final_mapping,
        normalizations=config.normalizations,
    )

    # Save user corrections to project alias registry
    corrections_saved = 0
    project_id = cached.get("project_id")
    if project_id and corrections:
        try:
            proj_uuid = uuid.UUID(project_id)
            result = await db.execute(select(Item).where(Item.id == proj_uuid))
            project = result.scalar_one_or_none()
            if project:
                from app.core.column_aliases import clean_column_name

                existing_aliases = project.properties.get(
                    "column_alias_corrections", {}
                )
                for col_name, corrected_prop in corrections.items():
                    if corrected_prop is not None:
                        cleaned = clean_column_name(col_name)
                        existing_aliases[cleaned] = corrected_prop
                        corrections_saved += 1
                project.properties = {
                    **project.properties,
                    "column_alias_corrections": existing_aliases,
                }
                await db.flush()
        except (ValueError, Exception):
            pass  # Non-critical: corrections not saved

    # Clean up cache
    _proposal_cache.pop(proposal_id, None)

    return MappingConfirmResponse(
        confirmed_config=confirmed_config,
        corrections_saved=corrections_saved,
        message=f"Mapping confirmed with {corrections_saved} corrections saved.",
    )


# ─── Main Import Endpoint (WP-6b: auto-mapping fallback) ────────


@router.post("/import", response_model=ImportResult, status_code=201)
async def import_file(
    file: UploadFile = File(...),
    source_item_id: str = Form(...),
    time_context_id: str = Form(...),
    mapping_config: str | None = Form(
        None, description="JSON-encoded ImportMappingConfig"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Import a file (Excel/CSV) and create source-attributed snapshots.

    Mapping resolution order (WP-6b Section 3.5):
      1. Explicit mapping_config in request → use as-is
      2. Stored mapping on source item → use as-is (repeat import)
      3. Neither provided → run auto-mapping service
         a. High confidence (all columns ≥ 0.8) → import proceeds, mapping stored
         b. Below threshold → return ProposedMapping for user review (422)

    For each row in the file:
      1. Match to existing item by identifier (exact → normalized)
      2. Create new item if no match found
      3. Upsert snapshot: (what=item, when=milestone, who=source)
      4. Ensure connection: source → item

    Also creates:
      - Source self-snapshot with import metadata
      - Import batch item to track this import
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

    # Check project access via source item
    project_id_check = await get_project_for_item(db, src_id)
    if project_id_check:
        await require_project_access(db, project_id_check, current_user)

    # Read file bytes
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Determine file type
    filename = file.filename or ""
    file_type = "csv" if filename.lower().endswith(".csv") else "excel"

    # ── Mapping resolution (WP-6b Section 3.5) ──────────────────

    mapping: ImportMappingConfig | None = None

    # Path 1: Explicit mapping_config in request
    if mapping_config:
        try:
            mapping = ImportMappingConfig(**json.loads(mapping_config))
        except (json.JSONDecodeError, Exception) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mapping_config JSON: {e}",
            )

    # Path 2: Stored mapping on source item
    if not mapping:
        stored = source_item.properties.get("import_mapping")
        if stored:
            mapping = ImportMappingConfig(**stored)

    # Path 3: Auto-mapping fallback (WP-6b)
    if not mapping:
        # Load user aliases
        user_aliases = None
        # Try to find project from source connections
        project_id_result = await db.execute(
            select(Connection.source_item_id).where(
                Connection.target_item_id == source_item.id
            )
        )
        parent_ids = project_id_result.scalars().all()
        for pid in parent_ids:
            parent_result = await db.execute(select(Item).where(Item.id == pid))
            parent = parent_result.scalar_one_or_none()
            if parent and parent.item_type == "project":
                user_aliases = await _load_user_aliases(db, parent.id)
                break

        proposed = propose_mapping(
            file_bytes=file_bytes,
            file_type=file_type,
            user_aliases=user_aliases,
        )

        # Path 3a: High confidence → proceed automatically
        if proposed.proposed_config and not proposed.needs_user_review:
            mapping = proposed.proposed_config
        # Path 3b: Below threshold → return proposal for review
        elif proposed.proposed_config:
            # Store as proposal and return 422
            proposal_id = uuid.uuid4()
            column_responses = [
                ColumnProposalResponse(
                    column_name=cp.column_name,
                    proposed_property=cp.proposed_property,
                    confidence=cp.confidence,
                    match_method=cp.match_method,
                    alternatives=cp.alternatives,
                )
                for cp in proposed.columns
            ]
            _proposal_cache[proposal_id] = {
                "proposed": proposed,
                "file_bytes": file_bytes,
                "file_type": file_type,
                "source_item_id": source_item_id,
            }
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Auto-mapping requires user review before import.",
                    "proposal_id": str(proposal_id),
                    "proposed_config": proposed.proposed_config.model_dump(),
                    "columns": [c.model_dump() for c in column_responses],
                    "unmatched_columns": proposed.unmatched_columns,
                    "overall_confidence": proposed.overall_confidence,
                },
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Could not determine file structure. "
                "Use POST /api/v1/import/analyze to preview the mapping, "
                "or provide an explicit mapping_config.",
            )

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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
