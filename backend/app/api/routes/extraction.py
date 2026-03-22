"""
API routes for WP-17: Specification Extraction — LLM Pipeline.

Endpoints:
  POST /api/v1/spec/extract                      — Trigger extraction
  GET  /api/v1/spec/extract/{batch_id}/review     — Review extraction results
  POST /api/v1/spec/extract/{batch_id}/confirm    — Confirm/correct extractions
  GET  /api/v1/spec/extract/{batch_id}            — Batch status
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.core import Item
from app.schemas.extraction import (
    CrossReferenceReviewItem,
    ExtractionBatchStatus,
    ExtractionConfirmRequest,
    ExtractionConfirmResponse,
    ExtractionItem,
    ExtractionReviewResponse,
    ExtractRequest,
    ExtractResponse,
    NounExtractionReview,
    SectionExtractionReview,
    UnrecognizedItem,
)
from app.services.extraction_service import run_extraction
from app.services.extraction_confirm_service import confirm_extractions

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── POST /spec/extract ──────────────────────────────────────────


@router.post("/spec/extract", response_model=ExtractResponse)
async def trigger_extraction(
    request: ExtractRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger LLM extraction for preprocessed specification sections.

    Requires a confirmed WP-16 preprocess batch. Creates an extraction_batch
    item, runs extraction per section, and stores results for review.
    """
    try:
        batch, results = await run_extraction(
            db=db,
            specification_id=request.specification_id,
            preprocess_batch_id=request.preprocess_batch_id,
            context_id=request.context_id,
            section_numbers=request.section_numbers,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        elif "not confirmed" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.exception(f"Extraction failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Extraction failed unexpectedly",
        )

    return ExtractResponse(
        batch_id=batch.id,
        status=batch.properties.get("status", "extracted"),
        sections_total=batch.properties.get("sections_total", 0),
    )


# ─── GET /spec/extract/{batch_id}/review ─────────────────────────


@router.get(
    "/spec/extract/{batch_id}/review",
    response_model=ExtractionReviewResponse,
)
async def review_extractions(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve extraction results for user review.

    Returns per-section extractions with confidence scores, source text
    citations, unrecognized terms, and navigable cross-references.
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
        raise HTTPException(status_code=404, detail="Extraction batch not found")

    props = batch.properties or {}
    extraction_results = props.get("extraction_results", {})
    sections_data = extraction_results.get("sections", {})

    # Load spec and context names for display
    spec_name = None
    context_name = None

    spec_id = props.get("specification_item_id")
    if spec_id:
        spec_result = await db.execute(select(Item).where(Item.id == uuid.UUID(spec_id)))
        spec_item = spec_result.scalar_one_or_none()
        if spec_item:
            spec_name = (spec_item.properties or {}).get("name", spec_item.identifier)

    ctx_id = props.get("context_id")
    if ctx_id:
        ctx_result = await db.execute(select(Item).where(Item.id == uuid.UUID(ctx_id)))
        ctx_item = ctx_result.scalar_one_or_none()
        if ctx_item:
            context_name = (ctx_item.properties or {}).get("name", ctx_item.identifier)

    # Build section reviews with navigability flags on cross-references
    sections: list[SectionExtractionReview] = []

    for section_num, section_data in sections_data.items():
        # Parse extractions
        extractions = [
            ExtractionItem(**e) for e in section_data.get("extractions", [])
        ]
        unrecognized = [
            UnrecognizedItem(**u) for u in section_data.get("unrecognized", [])
        ]

        # Resolve cross-reference navigability
        cross_refs: list[CrossReferenceReviewItem] = []
        for cr in section_data.get("cross_references", []):
            ref_section_num = cr.get("section_number", "")
            # Check if this section exists in the graph
            ref_result = await db.execute(
                select(Item).where(
                    and_(
                        Item.item_type == "spec_section",
                        Item.identifier == ref_section_num,
                    )
                )
            )
            ref_item = ref_result.scalar_one_or_none()

            cross_refs.append(CrossReferenceReviewItem(
                section_number=ref_section_num,
                relationship=cr.get("relationship", ""),
                source_text=cr.get("source_text", ""),
                navigable=ref_item is not None,
                section_item_id=ref_item.id if ref_item else None,
            ))

        # Get section title from spec_section item if available
        section_title = None
        title_result = await db.execute(
            select(Item).where(
                and_(
                    Item.item_type == "spec_section",
                    Item.identifier == section_num,
                )
            )
        )
        title_item = title_result.scalar_one_or_none()
        if title_item:
            section_title = (title_item.properties or {}).get("title")

        # Build noun-level review data (v2)
        noun_reviews: list[NounExtractionReview] = []
        for noun_data in section_data.get("nouns", []):
            # Build cross-ref review items for this noun
            noun_xrefs: list[CrossReferenceReviewItem] = []
            for ncr in noun_data.get("cross_references", []):
                nr_num = ncr.get("section_number", "")
                nr_result = await db.execute(
                    select(Item).where(
                        and_(
                            Item.item_type == "spec_section",
                            Item.identifier == nr_num,
                        )
                    )
                )
                nr_item = nr_result.scalar_one_or_none()
                noun_xrefs.append(CrossReferenceReviewItem(
                    section_number=nr_num,
                    relationship=ncr.get("relationship", ""),
                    source_text=ncr.get("source_text", ""),
                    navigable=nr_item is not None,
                    section_item_id=nr_item.id if nr_item else None,
                ))

            noun_reviews.append(NounExtractionReview(
                noun_phrase=noun_data.get("noun_phrase", ""),
                matched_type=noun_data.get("matched_type"),
                qualifiers=noun_data.get("qualifiers", {}),
                context=noun_data.get("context", ""),
                extractions=[
                    ExtractionItem(**e)
                    for e in noun_data.get("extractions", [])
                ],
                unrecognized=[
                    UnrecognizedItem(**u)
                    for u in noun_data.get("unrecognized", [])
                ],
                cross_references=noun_xrefs,
                attributed_elements=noun_data.get("attributed_elements", []),
                attribution_status=noun_data.get("attribution_status", "pending"),
            ))

        sections.append(SectionExtractionReview(
            section_number=section_num,
            section_title=section_title,
            status=section_data.get("status", "unknown"),
            nouns=noun_reviews,
            extractions=extractions,
            unrecognized=unrecognized,
            cross_references=cross_refs,
        ))

    return ExtractionReviewResponse(
        batch_id=batch.id,
        status=props.get("status", "unknown"),
        specification_name=spec_name,
        context_name=context_name,
        sections=sections,
    )


# ─── POST /spec/extract/{batch_id}/confirm ───────────────────────


@router.post(
    "/spec/extract/{batch_id}/confirm",
    response_model=ExtractionConfirmResponse,
)
async def confirm_extraction_results(
    batch_id: uuid.UUID,
    request: ExtractionConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm, correct, or reject extraction results.

    Processes user decisions per section. Promotes unrecognized terms
    to new PropertyDefs when requested. Stores confirmed results on
    the extraction batch for WP-18 handoff.
    """
    try:
        result = await confirm_extractions(
            db=db,
            batch_id=batch_id,
            confirmations=request.confirmations,
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
            detail="Extraction confirmation failed unexpectedly",
        )

    return ExtractionConfirmResponse(
        batch_id=batch_id,
        status="confirmed",
        extractions_confirmed=result["confirmed"],
        extractions_corrected=result["corrected"],
        extractions_rejected=result["rejected"],
        properties_promoted=result["promoted"],
    )


# ─── GET /spec/extract/{batch_id} ────────────────────────────────


@router.get(
    "/spec/extract/{batch_id}",
    response_model=ExtractionBatchStatus,
)
async def get_extraction_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve extraction batch status and summary counts.
    """
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
        raise HTTPException(status_code=404, detail="Extraction batch not found")

    props = batch.properties or {}

    return ExtractionBatchStatus(
        batch_id=batch.id,
        status=props.get("status", "unknown"),
        specification_item_id=props.get("specification_item_id"),
        preprocess_batch_id=props.get("preprocess_batch_id"),
        context_id=props.get("context_id"),
        sections_total=props.get("sections_total"),
        sections_extracted=props.get("sections_extracted"),
        sections_failed=props.get("sections_failed"),
    )
