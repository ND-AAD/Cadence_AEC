"""
Tests for WP-17.2/17.3: Extraction API Routes & Confirmation Service.

Covers:
  - API tests: trigger extraction, review, confirm, batch status
  - Confirmation service: confirm/correct/reject decisions,
    property promotion, idempotency guards, edge cases
  - HTTP error responses: 404, 400, 409
"""

import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
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
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════

SAMPLE_PART2_TEXT = """
PART 2 - PRODUCTS

2.1 METAL DOORS

A. Steel Doors: ANSI/SDI A250.8, Level 3, 16 gauge.
   1. Material: Hollow metal, cold-rolled steel.
   2. Finish: Factory applied rust-inhibitive primer.

B. Acoustic Performance:
   1. Doors shall have a minimum STC rating of 45.

C. Hardware: Per Section 08 71 00.
"""

SAMPLE_PART1_TEXT = """
PART 1 - GENERAL

1.1 RELATED SECTIONS:
    Section 08 71 00 - Door Hardware
"""

MOCK_LLM_RESPONSE = json.dumps(
    {
        "section_number": "08 11 00",
        "extractions": [
            {
                "property": "material",
                "element_type": "door",
                "assertion_type": "flat",
                "value": "hollow metal",
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
        ],
        "unrecognized": [
            {
                "term": "STC rating",
                "value": "45",
                "context": "door acoustic requirements",
                "source_text": "Doors shall have a minimum STC rating of 45.",
            }
        ],
        "cross_references": [
            {
                "section_number": "08 71 00",
                "relationship": "hardware requirements",
                "source_text": "Hardware: Per Section 08 71 00.",
            }
        ],
    }
)


_mock_llm_caller_multi_pass = make_multi_pass_mock(MOCK_LLM_RESPONSE)


@pytest_asyncio.fixture
async def extraction_setup(db_session, make_item, make_connection):
    """
    Create prerequisite items for extraction tests:
    specification, milestone, spec_section, and a confirmed preprocess batch.
    """
    spec = await make_item(
        "specification",
        "Test Specification",
        {
            "name": "Test Specification",
        },
    )
    milestone = await make_item(
        "milestone",
        "50CD",
        {
            "name": "50% Construction Documents",
            "ordinal": 500,
        },
    )
    section = await make_item(
        "spec_section",
        "08 11 00",
        {
            "title": "Metal Doors and Frames",
            "division": "08",
            "level": 2,
        },
    )
    pp_batch = await make_item(
        "preprocess_batch",
        "Preprocess-test.pdf",
        {
            "original_filename": "test.pdf",
            "status": "confirmed",
            "page_count": 10,
            "sections_identified": 1,
            "sections_matched": 1,
            "specification_item_id": str(spec.id),
        },
    )
    await make_connection(
        spec,
        section,
        {
            "confirmed_by": "user",
            "section_number": "08 11 00",
            "part2_text": SAMPLE_PART2_TEXT,
            "part1_text": SAMPLE_PART1_TEXT,
            "match_confidence": 1.0,
            "detected_title": "Metal Doors and Frames",
        },
    )

    return {
        "spec": spec,
        "milestone": milestone,
        "section": section,
        "pp_batch": pp_batch,
    }


@pytest_asyncio.fixture
async def extracted_batch(db_session, extraction_setup):
    """Create a fully extracted batch ready for review/confirmation."""
    data = extraction_setup
    batch, results = await run_extraction(
        db=db_session,
        specification_id=data["spec"].id,
        preprocess_batch_id=data["pp_batch"].id,
        context_id=data["milestone"].id,
        llm_caller=_mock_llm_caller_multi_pass,
    )
    return {**data, "batch": batch, "results": results}


# ═══════════════════════════════════════════════════════════════════
# API Tests — POST /spec/extract
# ═══════════════════════════════════════════════════════════════════


class TestTriggerExtractionAPI:
    """Test POST /api/v1/spec/extract endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_extraction_success(
        self, client: AsyncClient, extraction_setup
    ):
        data = extraction_setup
        # Note: the mock LLM isn't wired through the API endpoint directly;
        # we'd need to mock at a deeper level. Instead, test service directly
        # and use the API for error-path testing.
        pass

    @pytest.mark.asyncio
    async def test_trigger_extraction_missing_spec(
        self, client: AsyncClient, extraction_setup
    ):
        data = extraction_setup
        response = await client.post(
            "/api/v1/spec/extract",
            json={
                "specification_id": str(uuid.uuid4()),
                "preprocess_batch_id": str(data["pp_batch"].id),
                "context_id": str(data["milestone"].id),
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_extraction_missing_preprocess(
        self, client: AsyncClient, extraction_setup
    ):
        data = extraction_setup
        response = await client.post(
            "/api/v1/spec/extract",
            json={
                "specification_id": str(data["spec"].id),
                "preprocess_batch_id": str(uuid.uuid4()),
                "context_id": str(data["milestone"].id),
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_extraction_unconfirmed_preprocess(
        self,
        client: AsyncClient,
        extraction_setup,
        make_item,
    ):
        data = extraction_setup
        unconfirmed = await make_item(
            "preprocess_batch",
            "Unconfirmed",
            {
                "status": "identified",
            },
        )
        response = await client.post(
            "/api/v1/spec/extract",
            json={
                "specification_id": str(data["spec"].id),
                "preprocess_batch_id": str(unconfirmed.id),
                "context_id": str(data["milestone"].id),
            },
        )
        assert response.status_code == 400
        assert "not confirmed" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════
# API Tests — GET /spec/extract/{batch_id}/review
# ═══════════════════════════════════════════════════════════════════


class TestReviewExtractionAPI:
    """Test GET /api/v1/spec/extract/{batch_id}/review endpoint."""

    @pytest.mark.asyncio
    async def test_review_success(self, client: AsyncClient, extracted_batch):
        batch = extracted_batch["batch"]
        response = await client.get(f"/api/v1/spec/extract/{batch.id}/review")
        assert response.status_code == 200

        body = response.json()
        assert body["batch_id"] == str(batch.id)
        assert body["status"] == "extracted"
        assert len(body["sections"]) == 1

        section = body["sections"][0]
        assert section["section_number"] == "08 11 00"
        assert section["status"] == "extracted"
        assert len(section["extractions"]) == 2
        assert len(section["unrecognized"]) == 1
        assert len(section["cross_references"]) == 1

    @pytest.mark.asyncio
    async def test_review_includes_spec_name(
        self, client: AsyncClient, extracted_batch
    ):
        batch = extracted_batch["batch"]
        response = await client.get(f"/api/v1/spec/extract/{batch.id}/review")
        body = response.json()
        assert body["specification_name"] == "Test Specification"

    @pytest.mark.asyncio
    async def test_review_cross_reference_navigability(
        self,
        client: AsyncClient,
        extracted_batch,
        make_item,
    ):
        """Cross-references should be navigable if the referenced section exists."""
        batch = extracted_batch["batch"]

        # The cross-reference points to 08 71 00 — it doesn't exist yet
        response = await client.get(f"/api/v1/spec/extract/{batch.id}/review")
        body = response.json()
        cr = body["sections"][0]["cross_references"][0]
        assert cr["section_number"] == "08 71 00"
        assert cr["navigable"] is False
        assert cr["section_item_id"] is None

        # Now create the referenced section
        ref_section = await make_item(
            "spec_section",
            "08 71 00",
            {
                "title": "Door Hardware",
                "division": "08",
                "level": 2,
            },
        )

        # Review again
        response = await client.get(f"/api/v1/spec/extract/{batch.id}/review")
        body = response.json()
        cr = body["sections"][0]["cross_references"][0]
        assert cr["navigable"] is True
        assert cr["section_item_id"] == str(ref_section.id)

    @pytest.mark.asyncio
    async def test_review_batch_not_found(self, client: AsyncClient):
        response = await client.get(f"/api/v1/spec/extract/{uuid.uuid4()}/review")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_review_section_title_resolved(
        self, client: AsyncClient, extracted_batch
    ):
        """Section title should be resolved from the spec_section item."""
        batch = extracted_batch["batch"]
        response = await client.get(f"/api/v1/spec/extract/{batch.id}/review")
        body = response.json()
        section = body["sections"][0]
        assert section["section_title"] == "Metal Doors and Frames"


# ═══════════════════════════════════════════════════════════════════
# API Tests — GET /spec/extract/{batch_id}
# ═══════════════════════════════════════════════════════════════════


class TestBatchStatusAPI:
    """Test GET /api/v1/spec/extract/{batch_id} endpoint."""

    @pytest.mark.asyncio
    async def test_batch_status_success(self, client: AsyncClient, extracted_batch):
        batch = extracted_batch["batch"]
        response = await client.get(f"/api/v1/spec/extract/{batch.id}")
        assert response.status_code == 200

        body = response.json()
        assert body["batch_id"] == str(batch.id)
        assert body["status"] == "extracted"
        assert body["sections_total"] == 1
        assert body["sections_extracted"] == 1
        assert body["sections_failed"] == 0

    @pytest.mark.asyncio
    async def test_batch_status_not_found(self, client: AsyncClient):
        response = await client.get(f"/api/v1/spec/extract/{uuid.uuid4()}")
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# API Tests — POST /spec/extract/{batch_id}/confirm
# ═══════════════════════════════════════════════════════════════════


class TestConfirmExtractionAPI:
    """Test POST /api/v1/spec/extract/{batch_id}/confirm endpoint."""

    @pytest.mark.asyncio
    async def test_confirm_all_success(self, client: AsyncClient, extracted_batch):
        batch = extracted_batch["batch"]
        response = await client.post(
            f"/api/v1/spec/extract/{batch.id}/confirm",
            json={"confirmations": []},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "confirmed"
        assert body["extractions_confirmed"] == 2  # material + finish
        assert body["extractions_rejected"] == 0
        assert body["properties_promoted"] == 0

    @pytest.mark.asyncio
    async def test_confirm_with_decisions(self, client: AsyncClient, extracted_batch):
        batch = extracted_batch["batch"]
        response = await client.post(
            f"/api/v1/spec/extract/{batch.id}/confirm",
            json={
                "confirmations": [
                    {
                        "section_number": "08 11 00",
                        "extraction_decisions": [
                            {
                                "property": "material",
                                "element_type": "door",
                                "action": "confirm",
                            },
                            {
                                "property": "finish",
                                "element_type": "door",
                                "action": "reject",
                            },
                        ],
                        "unrecognized_decisions": [],
                    }
                ],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["extractions_confirmed"] == 1
        assert body["extractions_rejected"] == 1

    @pytest.mark.asyncio
    async def test_confirm_batch_not_found(self, client: AsyncClient):
        response = await client.post(
            f"/api/v1/spec/extract/{uuid.uuid4()}/confirm",
            json={"confirmations": []},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_confirm_already_confirmed(
        self, client: AsyncClient, extracted_batch
    ):
        batch = extracted_batch["batch"]
        # First confirmation
        await client.post(
            f"/api/v1/spec/extract/{batch.id}/confirm",
            json={"confirmations": []},
        )
        # Second confirmation — 409
        response = await client.post(
            f"/api/v1/spec/extract/{batch.id}/confirm",
            json={"confirmations": []},
        )
        assert response.status_code == 409
        assert "already confirmed" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════
# Confirmation Service Tests — Unit Level
# ═══════════════════════════════════════════════════════════════════


class TestConfirmationService:
    """Test confirm_extractions service function directly."""

    @pytest.mark.asyncio
    async def test_auto_confirm_no_decisions(self, db_session, extracted_batch):
        batch = extracted_batch["batch"]
        counts = await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[],
        )
        assert counts["confirmed"] == 2
        assert counts["corrected"] == 0
        assert counts["rejected"] == 0
        assert counts["promoted"] == 0

        # Verify batch status updated
        await db_session.refresh(batch)
        assert batch.properties["status"] == "confirmed"

    @pytest.mark.asyncio
    async def test_confirm_action(self, db_session, extracted_batch):
        batch = extracted_batch["batch"]
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
                            action="confirm",
                        ),
                    ],
                ),
            ],
        )
        assert counts["confirmed"] == 2
        assert counts["rejected"] == 0

    @pytest.mark.asyncio
    async def test_correct_action(self, db_session, extracted_batch):
        batch = extracted_batch["batch"]
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
                            action="correct",
                            corrected_value="galvanized steel",
                        ),
                    ],
                ),
            ],
        )
        assert counts["corrected"] == 1
        # finish auto-confirmed (no explicit decision)
        assert counts["confirmed"] == 1

        # Verify corrected value stored
        await db_session.refresh(batch)
        section_data = batch.properties["extraction_results"]["sections"]["08 11 00"]
        confirmed = section_data["confirmed_extractions"]
        material_ext = next(e for e in confirmed if e.get("property") == "material")
        assert material_ext["value"] == "galvanized steel"
        assert material_ext["original_value"] == "hollow metal"
        assert material_ext["action"] == "correct"

    @pytest.mark.asyncio
    async def test_reject_action(self, db_session, extracted_batch):
        batch = extracted_batch["batch"]
        counts = await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[
                SectionConfirmation(
                    section_number="08 11 00",
                    extraction_decisions=[
                        ExtractionDecision(
                            property="finish",
                            element_type="door",
                            action="reject",
                        ),
                    ],
                ),
            ],
        )
        assert counts["rejected"] == 1
        assert counts["confirmed"] == 1  # material auto-confirmed

        # Verify rejected extraction not in confirmed list
        await db_session.refresh(batch)
        section_data = batch.properties["extraction_results"]["sections"]["08 11 00"]
        confirmed = section_data["confirmed_extractions"]
        finish_exts = [e for e in confirmed if e.get("property") == "finish"]
        assert len(finish_exts) == 0

    @pytest.mark.asyncio
    async def test_promote_unrecognized_term(self, db_session, extracted_batch):
        batch = extracted_batch["batch"]
        counts = await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[
                SectionConfirmation(
                    section_number="08 11 00",
                    extraction_decisions=[],
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
        assert counts["confirmed"] == 2  # material + finish auto-confirmed

        # Verify property item created
        result = await db_session.execute(
            select(Item).where(
                and_(
                    Item.item_type == "property",
                    Item.identifier == "door/stc_rating",
                )
            )
        )
        prop_item = result.scalar_one_or_none()
        assert prop_item is not None
        assert prop_item.properties["data_type"] == "integer"
        assert prop_item.properties["label"] == "STC rating"

        # Verify promoted extraction added to confirmed list
        await db_session.refresh(batch)
        section_data = batch.properties["extraction_results"]["sections"]["08 11 00"]
        confirmed = section_data["confirmed_extractions"]
        promoted_exts = [e for e in confirmed if e.get("action") == "promoted"]
        assert len(promoted_exts) == 1
        assert promoted_exts[0]["property"] == "stc_rating"
        assert promoted_exts[0]["element_type"] == "door"

    @pytest.mark.asyncio
    async def test_skip_unrecognized_term(self, db_session, extracted_batch):
        batch = extracted_batch["batch"]
        counts = await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[
                SectionConfirmation(
                    section_number="08 11 00",
                    extraction_decisions=[],
                    unrecognized_decisions=[
                        UnrecognizedDecision(
                            term="STC rating",
                            action="skip",
                        ),
                    ],
                ),
            ],
        )
        assert counts["promoted"] == 0

        # Verify skipped term recorded
        await db_session.refresh(batch)
        section_data = batch.properties["extraction_results"]["sections"]["08 11 00"]
        assert "STC rating" in section_data["skipped_unrecognized"]

    @pytest.mark.asyncio
    async def test_promote_to_multiple_types(self, db_session, extracted_batch):
        batch = extracted_batch["batch"]
        counts = await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[
                SectionConfirmation(
                    section_number="08 11 00",
                    extraction_decisions=[],
                    unrecognized_decisions=[
                        UnrecognizedDecision(
                            term="STC rating",
                            action="add_as_property",
                            property_name="stc_rating",
                            target_types=["door", "room"],
                            data_type="integer",
                        ),
                    ],
                ),
            ],
        )
        assert counts["promoted"] == 1

        # Both property items should exist
        for parent_type in ["door", "room"]:
            result = await db_session.execute(
                select(Item).where(
                    and_(
                        Item.item_type == "property",
                        Item.identifier == f"{parent_type}/stc_rating",
                    )
                )
            )
            assert result.scalar_one_or_none() is not None

        # Two promoted entries in confirmed_extractions (one per target_type)
        await db_session.refresh(batch)
        section_data = batch.properties["extraction_results"]["sections"]["08 11 00"]
        confirmed = section_data["confirmed_extractions"]
        promoted = [e for e in confirmed if e.get("action") == "promoted"]
        assert len(promoted) == 2

    @pytest.mark.asyncio
    async def test_batch_not_found(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            await confirm_extractions(
                db=db_session,
                batch_id=uuid.uuid4(),
                confirmations=[],
            )

    @pytest.mark.asyncio
    async def test_batch_already_confirmed(self, db_session, extracted_batch):
        batch = extracted_batch["batch"]

        # First confirmation
        await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[],
        )

        # Second — should raise
        with pytest.raises(ValueError, match="already confirmed"):
            await confirm_extractions(
                db=db_session,
                batch_id=batch.id,
                confirmations=[],
            )

    @pytest.mark.asyncio
    async def test_batch_wrong_status(self, db_session, make_item):
        """Batch with status 'pending' is not ready for confirmation."""
        batch = await make_item(
            "extraction_batch",
            "Pending Batch",
            {
                "status": "pending",
                "extraction_results": {"sections": {}},
            },
        )

        with pytest.raises(ValueError, match="not ready for confirmation"):
            await confirm_extractions(
                db=db_session,
                batch_id=batch.id,
                confirmations=[],
            )

    @pytest.mark.asyncio
    async def test_failed_sections_skipped(self, db_session, make_item):
        """Sections with status 'failed' are skipped during confirmation."""
        batch = await make_item(
            "extraction_batch",
            "With Failed",
            {
                "status": "extracted",
                "extraction_results": {
                    "sections": {
                        "08 11 00": {
                            "status": "failed",
                            "error": "LLM call failed",
                            "extractions": [],
                        },
                        "09 91 00": {
                            "status": "extracted",
                            "extractions": [
                                {
                                    "property": "finish_wall",
                                    "element_type": "room",
                                    "assertion_type": "flat",
                                    "value": "latex paint",
                                    "confidence": 0.85,
                                    "source_text": "Walls: latex paint.",
                                }
                            ],
                            "unrecognized": [],
                        },
                    }
                },
            },
        )

        counts = await confirm_extractions(
            db=db_session,
            batch_id=batch.id,
            confirmations=[],
        )
        # Only the successful section's extraction auto-confirmed
        assert counts["confirmed"] == 1

    @pytest.mark.asyncio
    async def test_mixed_decisions(self, db_session, extracted_batch):
        """One confirm, one correct, one reject, one promote — all in one call."""
        batch = extracted_batch["batch"]
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
                            action="reject",
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
        assert counts["confirmed"] == 1
        assert counts["rejected"] == 1
        assert counts["promoted"] == 1

    @pytest.mark.asyncio
    async def test_property_name_auto_generated(self, db_session, extracted_batch):
        """When no property_name provided, auto-generate from term."""
        batch = extracted_batch["batch"]
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
                            property_name=None,  # Auto-generate
                            target_types=["door"],
                        ),
                    ],
                ),
            ],
        )
        assert counts["promoted"] == 1

        # Auto-generated name: "STC rating" → "stc_rating"
        result = await db_session.execute(
            select(Item).where(
                and_(
                    Item.item_type == "property",
                    Item.identifier == "door/stc_rating",
                )
            )
        )
        assert result.scalar_one_or_none() is not None
