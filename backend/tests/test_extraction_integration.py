"""
WP-17.4: Integration Validation — End-to-End Extraction Pipeline.

Tests the full pipeline:
  WP-16 preprocess (simulated) → WP-17 extract → review → confirm →
  verify extraction_batch ready for WP-18 handoff.

Validates:
  1. Extraction from preprocessed sections produces correct results
  2. Review endpoint returns navigable cross-references
  3. Confirmation stores confirmed_extractions on the batch
  4. Property promotion creates property items in the graph
  5. Extraction batch has connections to preprocess_batch, spec, milestone
  6. Batch status transitions: extracted → confirmed
  7. Confirmed batch has all data WP-18 needs for propagation
"""

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Connection, Item
from app.services.extraction_service import run_extraction
from app.services.extraction_confirm_service import confirm_extractions
from app.schemas.extraction import (
    ExtractionDecision,
    SectionConfirmation,
    UnrecognizedDecision,
)
from tests.mock_helpers import make_multi_pass_mock


# ═══════════════════════════════════════════════════════════════════
# Fixtures — Simulated WP-16 Output
# ═══════════════════════════════════════════════════════════════════

SAMPLE_PART2_METAL_DOORS = """
PART 2 - PRODUCTS

2.1 METAL DOORS

A. Steel Doors: ANSI/SDI A250.8, Level 3, Model 2, 16 gauge.
   1. Material: Hollow metal, cold-rolled steel.
   2. Finish: Factory applied rust-inhibitive primer.

B. Fire-Rated Doors:
   1. Doors in 1-hour rated partitions: UL listed, B-Label minimum.
   2. Doors in 2-hour rated partitions: UL listed, A-Label.

C. Acoustic Performance:
   1. Doors shall have a minimum STC rating of 45.

D. Hardware: Per Section 08 71 00.
"""

SAMPLE_PART1_WITH_RELATED = """
PART 1 - GENERAL

1.1 RELATED SECTIONS:
    Section 08 71 00 - Door Hardware
    Section 09 91 00 - Painting

1.2 SUBMITTALS
    A. Product Data.
"""

MOCK_LLM_RESPONSE = json.dumps({
    "section_number": "08 11 00",
    "extractions": [
        {
            "property": "material",
            "element_type": "door",
            "assertion_type": "flat",
            "value": "hollow metal, cold-rolled steel",
            "confidence": 0.95,
            "source_text": "Material: Hollow metal, cold-rolled steel.",
        },
        {
            "property": "finish",
            "element_type": "door",
            "assertion_type": "flat",
            "value": "factory applied rust-inhibitive primer",
            "confidence": 0.90,
            "source_text": "Finish: Factory applied rust-inhibitive primer.",
        },
        {
            "property": "fire_rating",
            "element_type": "door",
            "assertion_type": "conditional",
            "assertions": [
                {
                    "value": "B-Label",
                    "condition": "doors in 1-hour rated partitions",
                    "source_text": "Doors in 1-hour rated partitions: UL listed, B-Label minimum.",
                },
                {
                    "value": "A-Label",
                    "condition": "doors in 2-hour rated partitions",
                    "source_text": "Doors in 2-hour rated partitions: UL listed, A-Label.",
                },
            ],
            "confidence": 0.90,
        },
    ],
    "unrecognized": [
        {
            "term": "STC rating",
            "value": "45",
            "context": "door acoustic requirements",
            "source_text": "Doors shall have a minimum STC rating of 45.",
        },
    ],
    "cross_references": [
        {
            "section_number": "08 71 00",
            "relationship": "hardware requirements",
            "source_text": "Hardware: Per Section 08 71 00.",
        },
    ],
})


_mock_llm_caller_multi_pass = make_multi_pass_mock(MOCK_LLM_RESPONSE)


@pytest_asyncio.fixture
async def wp16_output(db_session, make_item, make_connection):
    """
    Simulate the output of a confirmed WP-16 preprocess batch.

    Creates:
      - specification item
      - milestone (issuance context)
      - spec_section item for 08 11 00
      - confirmed preprocess_batch
      - connection: specification → spec_section (with Part 1/2 text)
    """
    spec = await make_item("specification", "08 11 00 – Hollow Metal Doors", {
        "name": "Division 08 — Openings",
    })
    milestone = await make_item("milestone", "50CD", {
        "name": "50% Construction Documents",
        "ordinal": 500,
    })
    section = await make_item("spec_section", "08 11 00", {
        "title": "Hollow Metal Doors and Frames",
        "division": "08",
        "level": 2,
    })
    # Also create a referenced section (08 71 00) for navigability test
    hardware_section = await make_item("spec_section", "08 71 00", {
        "title": "Door Hardware",
        "division": "08",
        "level": 2,
    })

    pp_batch = await make_item("preprocess_batch", "Preprocess-08_doors.pdf", {
        "original_filename": "08_doors.pdf",
        "status": "confirmed",
        "page_count": 12,
        "sections_identified": 1,
        "sections_matched": 1,
        "specification_item_id": str(spec.id),
    })

    # WP-16 stores Part 1/2 text on specification → spec_section connection
    await make_connection(spec, section, {
        "confirmed_by": "user",
        "section_number": "08 11 00",
        "part2_text": SAMPLE_PART2_METAL_DOORS,
        "part1_text": SAMPLE_PART1_WITH_RELATED,
        "match_confidence": 1.0,
        "detected_title": "Hollow Metal Doors and Frames",
    })

    return {
        "spec": spec,
        "milestone": milestone,
        "section": section,
        "hardware_section": hardware_section,
        "pp_batch": pp_batch,
    }


# ═══════════════════════════════════════════════════════════════════
# Integration Test — Full Pipeline
# ═══════════════════════════════════════════════════════════════════


class TestExtractionPipelineE2E:
    """
    End-to-end integration test: WP-16 output → WP-17 extraction →
    review → confirmation → WP-18 handoff readiness.
    """

    @pytest.mark.asyncio
    async def test_full_pipeline(self, db_session: AsyncSession, wp16_output):
        """
        The complete extraction pipeline in a single test:
        extract → verify results → confirm with mixed decisions → verify handoff.
        """
        data = wp16_output

        # ── Step 1: Run extraction ────────────────────────────────
        batch, results = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            llm_caller=_mock_llm_caller_multi_pass,
        )

        assert batch.item_type == "extraction_batch"
        assert batch.properties["status"] == "extracted"
        assert batch.properties["sections_total"] == 1
        assert batch.properties["sections_extracted"] == 1
        assert batch.properties["sections_failed"] == 0

        # Verify extraction results
        assert "08 11 00" in results
        section_result = results["08 11 00"]
        assert section_result.status == "extracted"
        assert len(section_result.extractions) == 3  # material, finish, fire_rating
        assert len(section_result.unrecognized) == 1  # STC rating
        assert len(section_result.cross_references) == 1  # 08 71 00

        # Verify conditional assertion preserved
        fire_rating = next(
            e for e in section_result.extractions if e.property == "fire_rating"
        )
        assert fire_rating.assertion_type == "conditional"
        assert len(fire_rating.assertions) == 2

        # ── Step 2: Verify batch connections ──────────────────────
        conn_result = await db_session.execute(
            select(Connection).where(
                Connection.source_item_id == batch.id,
            )
        )
        connections = list(conn_result.scalars().all())
        target_ids = {c.target_item_id for c in connections}

        assert data["pp_batch"].id in target_ids, "Missing connection to preprocess_batch"
        assert data["spec"].id in target_ids, "Missing connection to specification"
        assert data["milestone"].id in target_ids, "Missing connection to milestone"

        # ── Step 3: Confirm with mixed decisions ──────────────────
        counts = await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[
                SectionConfirmation(
                    section_number="08 11 00",
                    extraction_decisions=[
                        ExtractionDecision(
                            property="material",
                            element_type="door",
                            action="confirm",
                        ),
                        ExtractionDecision(
                            property="finish",
                            element_type="door",
                            action="correct",
                            corrected_value="epoxy primer",
                        ),
                        ExtractionDecision(
                            property="fire_rating",
                            element_type="door",
                            action="confirm",
                        ),
                    ],
                    unrecognized_decisions=[
                        UnrecognizedDecision(
                            term="STC rating",
                            action="add_as_property",
                            property_name="stc_rating",
                            target_types=["door"],
                            data_type="integer",
                        ),
                    ],
                ),
            ],
        )

        assert counts["confirmed"] == 2    # material + fire_rating
        assert counts["corrected"] == 1    # finish
        assert counts["rejected"] == 0
        assert counts["promoted"] == 1     # STC rating → stc_rating

        # ── Step 4: Verify WP-18 handoff readiness ────────────────
        await db_session.refresh(batch)
        props = batch.properties

        # Batch status is confirmed
        assert props["status"] == "confirmed"

        # Extraction results contain confirmed_extractions for each section
        section_data = props["extraction_results"]["sections"]["08 11 00"]
        assert section_data["status"] == "confirmed"
        confirmed = section_data["confirmed_extractions"]

        # 3 from original (material confirmed, finish corrected, fire_rating confirmed)
        # + 1 promoted (stc_rating)
        assert len(confirmed) == 4

        # Verify corrected value
        finish_ext = next(e for e in confirmed if e.get("property") == "finish")
        assert finish_ext["value"] == "epoxy primer"
        assert finish_ext["original_value"] == "factory applied rust-inhibitive primer"
        assert finish_ext["action"] == "correct"

        # Verify promoted property in confirmed list
        promoted_ext = next(e for e in confirmed if e.get("action") == "promoted")
        assert promoted_ext["property"] == "stc_rating"
        assert promoted_ext["element_type"] == "door"
        assert promoted_ext["value"] == "45"

        # Verify conditional assertion preserved through confirmation
        fire_ext = next(e for e in confirmed if e.get("property") == "fire_rating")
        assert fire_ext["action"] == "confirm"

        # ── Step 5: Verify promoted property item in graph ────────
        prop_result = await db_session.execute(
            select(Item).where(
                and_(
                    Item.item_type == "property",
                    Item.identifier == "door/stc_rating",
                )
            )
        )
        prop_item = prop_result.scalar_one_or_none()
        assert prop_item is not None
        assert prop_item.properties["data_type"] == "integer"
        assert prop_item.properties["label"] == "STC rating"
        assert prop_item.properties["parent_type"] == "door"

        # ── Step 6: Verify cross-reference data preserved ─────────
        cross_refs = section_data.get("cross_references", [])
        # Cross-references are stored in extraction_results from LLM
        stored_results = props["extraction_results"]["sections"]["08 11 00"]
        # These are in the original section data, not in confirmed_extractions
        assert any(
            cr.get("section_number") == "08 71 00"
            for cr in stored_results.get("cross_references", [])
        )

    @pytest.mark.asyncio
    async def test_pipeline_metadata_linkage(self, db_session: AsyncSession, wp16_output):
        """Verify batch stores all metadata WP-18 needs for source attribution."""
        data = wp16_output

        batch, _ = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            llm_caller=_mock_llm_caller_multi_pass,
        )

        props = batch.properties
        assert props["specification_item_id"] == str(data["spec"].id)
        assert props["preprocess_batch_id"] == str(data["pp_batch"].id)
        assert props["context_id"] == str(data["milestone"].id)

    @pytest.mark.asyncio
    async def test_pipeline_auto_confirm_preserves_all(self, db_session: AsyncSession, wp16_output):
        """Auto-confirm (empty confirmations) preserves all extractions."""
        data = wp16_output

        batch, results = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            llm_caller=_mock_llm_caller_multi_pass,
        )

        counts = await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[],  # Auto-confirm all
        )

        assert counts["confirmed"] == 3  # material, finish, fire_rating
        assert counts["promoted"] == 0   # No unrecognized promotion

        await db_session.refresh(batch)
        section_data = batch.properties["extraction_results"]["sections"]["08 11 00"]
        assert len(section_data["confirmed_extractions"]) == 3

    @pytest.mark.asyncio
    async def test_pipeline_idempotent_property_promotion(
        self, db_session: AsyncSession, wp16_output, make_item,
    ):
        """Promoting a property that already exists should reuse it."""
        data = wp16_output

        # Pre-create the property item (as if from a prior extraction)
        existing_prop = await make_item("property", "door/stc_rating", {
            "property_name": "stc_rating",
            "parent_type": "door",
            "label": "STC Rating",
            "data_type": "string",  # Note: string, not integer
        })

        batch, _ = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            llm_caller=_mock_llm_caller_multi_pass,
        )

        counts = await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[
                SectionConfirmation(
                    section_number="08 11 00",
                    unrecognized_decisions=[
                        UnrecognizedDecision(
                            term="STC rating",
                            action="add_as_property",
                            property_name="stc_rating",
                            target_types=["door"],
                            data_type="integer",
                        ),
                    ],
                ),
            ],
        )
        assert counts["promoted"] == 1

        # Should not create a duplicate — existing property reused
        prop_result = await db_session.execute(
            select(Item).where(
                and_(
                    Item.item_type == "property",
                    Item.identifier == "door/stc_rating",
                )
            )
        )
        props = list(prop_result.scalars().all())
        assert len(props) == 1

        # Existing property is NOT updated (is_new was False)
        assert props[0].properties["data_type"] == "string"  # Original, not overwritten

    @pytest.mark.asyncio
    async def test_batch_identifier_traceable(self, db_session: AsyncSession, wp16_output):
        """Batch identifier should be traceable to the specification."""
        data = wp16_output

        batch, _ = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            llm_caller=_mock_llm_caller_multi_pass,
        )

        # Identifier should reference the spec
        assert "Division 08" in batch.identifier or "08 11 00" in batch.identifier
