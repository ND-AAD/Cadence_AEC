"""
API routes for WP-16: Specification Preprocessing – PDF to Sections.

Endpoints:
  POST /api/v1/spec/preprocess               — Upload PDF, get identified sections
  POST /api/v1/spec/preprocess/{batch_id}/confirm-sections — Confirm sections
  GET  /api/v1/spec/preprocess/{batch_id}     — Get batch status
"""

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.core import Item
from app.schemas.spec_preprocess import (
    ConfirmSectionsRequest,
    ConfirmSectionsResponse,
    IdentifiedDocument,
    PreprocessBatchStatus,
    SpecPreprocessResponse,
)
from app.services.spec_preprocess_service import (
    confirm_sections,
    preprocess_specification_pdf,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── POST /spec/preprocess ─────────────────────────────────────


@router.post("/spec/preprocess", response_model=SpecPreprocessResponse)
async def preprocess_pdf(
    file: UploadFile = File(...),
    spec_name: str = Form(...),
    hint_division: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a specification PDF for preprocessing.

    Extracts text, detects MasterFormat section boundaries,
    identifies Part 1/2/3 content, and matches against seeded
    MasterFormat items.

    Returns identified sections for user confirmation.
    """
    # Validate file type
    if file.content_type and file.content_type != "application/pdf":
        # Allow octet-stream as fallback (common for programmatic uploads)
        if file.content_type not in ("application/pdf", "application/octet-stream"):
            raise HTTPException(
                status_code=400,
                detail=f"Expected PDF file, got {file.content_type}",
            )

    # Read file bytes
    try:
        pdf_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    filename = file.filename or "unknown.pdf"

    # Run preprocessing pipeline
    try:
        batch_item, document = await preprocess_specification_pdf(
            db=db,
            pdf_bytes=pdf_bytes,
            filename=filename,
            hint_division=hint_division,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Preprocessing failed for {filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Preprocessing failed unexpectedly",
        )

    return SpecPreprocessResponse(
        batch_id=batch_item.id,
        document=document,
    )


# ─── POST /spec/preprocess/{batch_id}/confirm-sections ──────────


@router.post(
    "/spec/preprocess/{batch_id}/confirm-sections",
    response_model=ConfirmSectionsResponse,
)
async def confirm_preprocess_sections(
    batch_id: uuid.UUID,
    request: ConfirmSectionsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm identified sections after user review.

    Creates or uses a specification item and establishes connections
    from the specification to confirmed MasterFormat section items.
    Part 2 text is stored in connection properties for WP-17.
    """
    try:
        spec_item, sections_confirmed, connections_created = await confirm_sections(
            db=db,
            batch_id=batch_id,
            specification_item_id=request.specification_item_id,
            spec_name=request.spec_name,
            confirmations=request.section_confirmations,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        elif "already confirmed" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.exception(f"Confirmation failed for batch {batch_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Section confirmation failed unexpectedly",
        )

    return ConfirmSectionsResponse(
        batch_id=batch_id,
        specification_item_id=spec_item.id,
        sections_confirmed=sections_confirmed,
        connections_created=connections_created,
    )


# ─── GET /spec/preprocess/{batch_id} ───────────────────────────


@router.get(
    "/spec/preprocess/{batch_id}",
    response_model=PreprocessBatchStatus,
)
async def get_preprocess_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve preprocessing batch status and stored document.
    """
    result = await db.execute(
        select(Item).where(
            and_(
                Item.id == batch_id,
                Item.item_type == "preprocess_batch",
            )
        )
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=404, detail="Preprocess batch not found")

    props = batch.properties if isinstance(batch.properties, dict) else {}

    # Parse stored document if available
    document = None
    doc_json = props.get("document_json")
    if doc_json:
        try:
            document = IdentifiedDocument.model_validate_json(doc_json)
        except Exception:
            logger.warning(f"Failed to parse stored document for batch {batch_id}")

    return PreprocessBatchStatus(
        batch_id=batch.id,
        status=props.get("status", "unknown"),
        original_filename=props.get("original_filename"),
        page_count=props.get("page_count"),
        sections_identified=props.get("sections_identified"),
        sections_matched=props.get("sections_matched"),
        document=document,
    )
