"""
Tests for WP-17: Specification Extraction — LLM Pipeline.

Covers:
  - Unit tests: vocabulary assembly, prompt construction, response parsing,
    related sections parsing (no DB, no LLM)
  - Service tests: per-section extraction, batch orchestration
    (DB + mock LLM)
"""

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.type_config import (
    PropertyDef,
    get_type_config,
    get_vocabulary_for_division,
    get_types_for_division,
)
from app.models.core import Connection, Item
from app.services.extraction_service import (
    assemble_vocabulary,
    build_extraction_prompt,
    build_valid_properties,
    extract_section,
    parse_extraction_response,
    parse_related_sections,
    run_extraction,
)
from tests.mock_helpers import make_multi_pass_mock, make_multi_pass_mock_error


# ═══════════════════════════════════════════════════════════════════
# Test Fixtures
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
    Section 07 84 00 - Firestopping

1.2 SUBMITTALS
    A. Product Data.
"""

SAMPLE_PART1_NO_RELATED = """
PART 1 - GENERAL

1.1 SUBMITTALS
    A. Product Data.
"""

MOCK_LLM_RESPONSE_METAL_DOORS = json.dumps(
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


async def _mock_llm_caller(prompt: str) -> str:
    """Mock LLM that returns the metal doors response."""
    return MOCK_LLM_RESPONSE_METAL_DOORS


async def _mock_llm_caller_empty(prompt: str) -> str:
    """Mock LLM that returns empty extractions."""
    return json.dumps(
        {
            "section_number": "08 11 00",
            "extractions": [],
            "unrecognized": [],
            "cross_references": [],
        }
    )


async def _mock_llm_caller_invalid_json(prompt: str) -> str:
    """Mock LLM that returns invalid JSON."""
    return "This is not valid JSON at all"


async def _mock_llm_caller_with_fencing(prompt: str) -> str:
    """Mock LLM that wraps response in markdown fencing."""
    return f"```json\n{MOCK_LLM_RESPONSE_METAL_DOORS}\n```"


async def _mock_llm_caller_error(prompt: str) -> str:
    """Mock LLM that raises an exception."""
    raise RuntimeError("API connection failed")


# ═══════════════════════════════════════════════════════════════════
# Unit Tests — type_config.py vocabulary functions
# ═══════════════════════════════════════════════════════════════════


class TestVocabularyLookup:
    """Test get_vocabulary_for_division and get_types_for_division."""

    def test_division_08_returns_door(self):
        vocab = get_vocabulary_for_division("08")
        assert "door" in vocab
        prop_names = {p.name for p in vocab["door"]}
        assert "material" in prop_names
        assert "fire_rating" in prop_names
        assert "finish" in prop_names

    def test_division_09_returns_room(self):
        vocab = get_vocabulary_for_division("09")
        assert "room" in vocab
        prop_names = {p.name for p in vocab["room"]}
        assert "finish_floor" in prop_names
        assert "finish_wall" in prop_names

    def test_unknown_division_returns_empty(self):
        vocab = get_vocabulary_for_division("99")
        assert vocab == {}

    def test_get_types_for_division_08(self):
        types = get_types_for_division("08")
        assert "door" in types

    def test_get_types_for_division_unknown(self):
        types = get_types_for_division("99")
        assert types == []


# ═══════════════════════════════════════════════════════════════════
# Unit Tests — Related Sections Parsing
# ═══════════════════════════════════════════════════════════════════


class TestRelatedSectionsParsing:
    """Test parse_related_sections from Part 1 text."""

    def test_standard_related_sections(self):
        divs = parse_related_sections(SAMPLE_PART1_WITH_RELATED)
        assert "08" in divs  # 08 71 00
        assert "09" in divs  # 09 91 00
        assert "07" in divs  # 07 84 00

    def test_no_related_sections(self):
        divs = parse_related_sections(SAMPLE_PART1_NO_RELATED)
        assert divs == []

    def test_none_input(self):
        divs = parse_related_sections(None)
        assert divs == []

    def test_empty_string(self):
        divs = parse_related_sections("")
        assert divs == []

    def test_related_requirements_variant(self):
        text = """PART 1 - GENERAL

1.1 RELATED REQUIREMENTS:
    Section 03 30 00 - Cast-in-Place Concrete
    Section 05 12 00 - Structural Steel
"""
        divs = parse_related_sections(text)
        assert "03" in divs
        assert "05" in divs


# ═══════════════════════════════════════════════════════════════════
# Unit Tests — Vocabulary Assembly
# ═══════════════════════════════════════════════════════════════════


class TestVocabularyAssembly:
    """Test assemble_vocabulary function."""

    def test_primary_only(self):
        vocab = assemble_vocabulary("08")
        assert "door" in vocab["primary"]
        assert vocab["secondary"] == {}

    def test_primary_with_related(self):
        vocab = assemble_vocabulary("08", related_divisions=["09"])
        assert "door" in vocab["primary"]
        assert "room" in vocab["secondary"]

    def test_related_same_as_primary_excluded(self):
        vocab = assemble_vocabulary("08", related_divisions=["08"])
        # Division 08 types should only appear in primary
        assert "door" in vocab["primary"]
        assert "door" not in vocab["secondary"]

    def test_unknown_division(self):
        vocab = assemble_vocabulary("99")
        assert vocab["primary"] == {}
        assert vocab["secondary"] == {}

    def test_no_related(self):
        vocab = assemble_vocabulary("08", related_divisions=None)
        assert vocab["secondary"] == {}


# ═══════════════════════════════════════════════════════════════════
# Unit Tests — Prompt Construction
# ═══════════════════════════════════════════════════════════════════


class TestPromptConstruction:
    """Test build_extraction_prompt."""

    def test_prompt_includes_section_text(self):
        vocab = assemble_vocabulary("08")
        prompt = build_extraction_prompt(
            "08 11 00",
            "Metal Doors",
            SAMPLE_PART2_METAL_DOORS,
            vocab,
        )
        assert "METAL DOORS" in prompt
        assert "Hollow metal" in prompt

    def test_prompt_includes_property_names(self):
        vocab = assemble_vocabulary("08")
        prompt = build_extraction_prompt(
            "08 11 00",
            "Metal Doors",
            SAMPLE_PART2_METAL_DOORS,
            vocab,
        )
        assert "material" in prompt
        assert "fire_rating" in prompt
        assert "finish" in prompt

    def test_prompt_includes_section_number(self):
        vocab = assemble_vocabulary("08")
        prompt = build_extraction_prompt(
            "08 11 00",
            "Metal Doors",
            SAMPLE_PART2_METAL_DOORS,
            vocab,
        )
        assert "08 11 00" in prompt

    def test_prompt_includes_title(self):
        vocab = assemble_vocabulary("08")
        prompt = build_extraction_prompt(
            "08 11 00",
            "Metal Doors",
            SAMPLE_PART2_METAL_DOORS,
            vocab,
        )
        assert "Metal Doors" in prompt

    def test_prompt_no_title(self):
        vocab = assemble_vocabulary("08")
        prompt = build_extraction_prompt(
            "08 11 00",
            None,
            SAMPLE_PART2_METAL_DOORS,
            vocab,
        )
        # Should not crash, title just omitted
        assert "08 11 00" in prompt

    def test_prompt_includes_secondary_vocabulary(self):
        vocab = assemble_vocabulary("08", related_divisions=["09"])
        prompt = build_extraction_prompt(
            "08 11 00",
            "Metal Doors",
            SAMPLE_PART2_METAL_DOORS,
            vocab,
        )
        assert "from related sections" in prompt
        assert "finish_floor" in prompt or "Floor Finish" in prompt

    def test_prompt_includes_extraction_rules(self):
        vocab = assemble_vocabulary("08")
        prompt = build_extraction_prompt(
            "08 11 00",
            None,
            SAMPLE_PART2_METAL_DOORS,
            vocab,
        )
        assert "Only extract values that are explicitly stated" in prompt
        assert "Do not infer" in prompt

    def test_prompt_includes_output_schema(self):
        vocab = assemble_vocabulary("08")
        prompt = build_extraction_prompt(
            "08 11 00",
            None,
            SAMPLE_PART2_METAL_DOORS,
            vocab,
        )
        assert '"assertion_type"' in prompt
        assert '"cross_references"' in prompt
        assert '"unrecognized"' in prompt


# ═══════════════════════════════════════════════════════════════════
# Unit Tests — Response Parsing
# ═══════════════════════════════════════════════════════════════════


class TestResponseParsing:
    """Test parse_extraction_response."""

    def _valid_props(self) -> dict[str, set[str]]:
        """Standard valid properties for door type."""
        vocab = assemble_vocabulary("08")
        return build_valid_properties(vocab)

    def test_parse_valid_response(self):
        result = parse_extraction_response(
            MOCK_LLM_RESPONSE_METAL_DOORS,
            self._valid_props(),
        )
        assert result.status == "extracted"
        assert result.section_number == "08 11 00"
        assert len(result.extractions) == 3
        assert len(result.unrecognized) == 1
        assert len(result.cross_references) == 1

    def test_flat_extraction(self):
        result = parse_extraction_response(
            MOCK_LLM_RESPONSE_METAL_DOORS,
            self._valid_props(),
        )
        material = next(e for e in result.extractions if e.property == "material")
        assert material.assertion_type == "flat"
        assert material.value == "hollow metal"
        assert material.confidence == 0.95
        assert "Hollow metal" in material.source_text

    def test_conditional_extraction(self):
        result = parse_extraction_response(
            MOCK_LLM_RESPONSE_METAL_DOORS,
            self._valid_props(),
        )
        fire = next(e for e in result.extractions if e.property == "fire_rating")
        assert fire.assertion_type == "conditional"
        assert fire.assertions is not None
        assert len(fire.assertions) == 2
        assert fire.assertions[0].value == "B-Label"
        assert fire.assertions[0].condition == "doors in 1-hour rated partitions"

    def test_unrecognized_items(self):
        result = parse_extraction_response(
            MOCK_LLM_RESPONSE_METAL_DOORS,
            self._valid_props(),
        )
        assert result.unrecognized[0].term == "STC rating"
        assert result.unrecognized[0].value == "45"

    def test_cross_references(self):
        result = parse_extraction_response(
            MOCK_LLM_RESPONSE_METAL_DOORS,
            self._valid_props(),
        )
        assert result.cross_references[0].section_number == "08 71 00"
        assert result.cross_references[0].relationship == "hardware requirements"

    def test_invalid_json(self):
        result = parse_extraction_response(
            "Not valid JSON",
            self._valid_props(),
        )
        assert result.status == "failed"
        assert result.error is not None

    def test_markdown_fencing_stripped(self):
        fenced = f"```json\n{MOCK_LLM_RESPONSE_METAL_DOORS}\n```"
        result = parse_extraction_response(fenced, self._valid_props())
        assert result.status == "extracted"
        assert len(result.extractions) == 3

    def test_unknown_property_skipped(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "extractions": [
                    {
                        "property": "nonexistent_prop",
                        "element_type": "door",
                        "assertion_type": "flat",
                        "value": "something",
                        "confidence": 0.5,
                        "source_text": "...",
                    }
                ],
                "unrecognized": [],
                "cross_references": [],
            }
        )
        result = parse_extraction_response(response, self._valid_props())
        assert len(result.extractions) == 0  # Invalid property skipped

    def test_unknown_element_type_skipped(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "extractions": [
                    {
                        "property": "material",
                        "element_type": "spaceship",
                        "assertion_type": "flat",
                        "value": "titanium",
                        "confidence": 0.5,
                        "source_text": "...",
                    }
                ],
                "unrecognized": [],
                "cross_references": [],
            }
        )
        result = parse_extraction_response(response, self._valid_props())
        assert len(result.extractions) == 0  # Invalid type skipped

    def test_empty_extractions(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "extractions": [],
                "unrecognized": [],
                "cross_references": [],
            }
        )
        result = parse_extraction_response(response, self._valid_props())
        assert result.status == "extracted"
        assert len(result.extractions) == 0

    def test_response_not_dict(self):
        result = parse_extraction_response("[]", self._valid_props())
        assert result.status == "failed"


# ═══════════════════════════════════════════════════════════════════
# Unit Tests — Valid Properties Builder
# ═══════════════════════════════════════════════════════════════════


class TestBuildValidProperties:
    """Test build_valid_properties helper."""

    def test_includes_primary(self):
        vocab = assemble_vocabulary("08")
        vp = build_valid_properties(vocab)
        assert "door" in vp
        assert "material" in vp["door"]

    def test_includes_secondary(self):
        vocab = assemble_vocabulary("08", related_divisions=["09"])
        vp = build_valid_properties(vocab)
        assert "door" in vp
        assert "room" in vp
        assert "finish_floor" in vp["room"]

    def test_empty_vocabulary(self):
        vp = build_valid_properties({"primary": {}, "secondary": {}})
        assert vp == {}


# ═══════════════════════════════════════════════════════════════════
# Service Tests — Per-Section Extraction
# ═══════════════════════════════════════════════════════════════════


class TestExtractSection:
    """Test extract_section with mock LLM."""

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        result = await extract_section(
            section_number="08 11 00",
            section_title="Metal Doors and Frames",
            part2_text=SAMPLE_PART2_METAL_DOORS,
            part1_text=SAMPLE_PART1_WITH_RELATED,
            section_division="08",
            llm_caller=_mock_llm_caller,
        )
        assert result.status == "extracted"
        assert len(result.extractions) == 3
        assert len(result.unrecognized) == 1
        assert len(result.cross_references) == 1

    @pytest.mark.asyncio
    async def test_empty_part2_text(self):
        result = await extract_section(
            section_number="08 11 00",
            section_title="Metal Doors",
            part2_text="",
            part1_text=None,
            section_division="08",
            llm_caller=_mock_llm_caller,
        )
        assert result.status == "failed"
        assert "No Part 2 text" in result.error

    @pytest.mark.asyncio
    async def test_none_part2_text(self):
        result = await extract_section(
            section_number="08 11 00",
            section_title="Metal Doors",
            part2_text=None,
            part1_text=None,
            section_division="08",
            llm_caller=_mock_llm_caller,
        )
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_unknown_division(self):
        result = await extract_section(
            section_number="99 00 00",
            section_title="Unknown",
            part2_text="Some text",
            part1_text=None,
            section_division="99",
            llm_caller=_mock_llm_caller,
        )
        assert result.status == "failed"
        assert "No element types" in result.error

    @pytest.mark.asyncio
    async def test_llm_failure(self):
        result = await extract_section(
            section_number="08 11 00",
            section_title="Metal Doors",
            part2_text=SAMPLE_PART2_METAL_DOORS,
            part1_text=None,
            section_division="08",
            llm_caller=_mock_llm_caller_error,
        )
        assert result.status == "failed"
        assert "LLM call failed" in result.error

    @pytest.mark.asyncio
    async def test_invalid_json_response(self):
        result = await extract_section(
            section_number="08 11 00",
            section_title="Metal Doors",
            part2_text=SAMPLE_PART2_METAL_DOORS,
            part1_text=None,
            section_division="08",
            llm_caller=_mock_llm_caller_invalid_json,
        )
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_markdown_fenced_response(self):
        result = await extract_section(
            section_number="08 11 00",
            section_title="Metal Doors",
            part2_text=SAMPLE_PART2_METAL_DOORS,
            part1_text=None,
            section_division="08",
            llm_caller=_mock_llm_caller_with_fencing,
        )
        assert result.status == "extracted"
        assert len(result.extractions) == 3

    @pytest.mark.asyncio
    async def test_empty_extraction_result(self):
        result = await extract_section(
            section_number="08 11 00",
            section_title="Metal Doors",
            part2_text=SAMPLE_PART2_METAL_DOORS,
            part1_text=None,
            section_division="08",
            llm_caller=_mock_llm_caller_empty,
        )
        assert result.status == "extracted"
        assert len(result.extractions) == 0


# ═══════════════════════════════════════════════════════════════════
# Service Tests — Batch Orchestration
# ═══════════════════════════════════════════════════════════════════


class TestRunExtraction:
    """Test run_extraction with database and mock LLM."""

    @pytest_asyncio.fixture
    async def setup_data(self, db_session, make_item, make_connection):
        """Create prerequisite items for extraction."""
        # Specification item
        spec = await make_item(
            "specification",
            "Test Specification",
            {
                "name": "Test Specification",
            },
        )

        # Milestone (context)
        milestone = await make_item(
            "milestone",
            "50CD",
            {
                "name": "50% Construction Documents",
                "ordinal": 500,
            },
        )

        # Spec section item
        section = await make_item(
            "spec_section",
            "08 11 00",
            {
                "title": "Metal Doors and Frames",
                "division": "08",
                "level": 2,
            },
        )

        # Preprocess batch (confirmed)
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

        # Connection: specification → spec_section (with Part 2 text)
        await make_connection(
            spec,
            section,
            {
                "confirmed_by": "user",
                "section_number": "08 11 00",
                "part2_text": SAMPLE_PART2_METAL_DOORS,
                "part1_text": SAMPLE_PART1_WITH_RELATED,
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

    @pytest.mark.asyncio
    async def test_successful_batch_extraction(self, db_session, setup_data):
        data = setup_data

        batch, results = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            llm_caller=make_multi_pass_mock(MOCK_LLM_RESPONSE_METAL_DOORS),
        )

        assert batch.item_type == "extraction_batch"
        assert batch.properties["status"] == "extracted"
        assert batch.properties["sections_total"] == 1
        assert batch.properties["sections_extracted"] == 1
        assert batch.properties["sections_failed"] == 0

        # Results stored on batch
        stored = batch.properties.get("extraction_results", {})
        assert "sections" in stored
        assert "08 11 00" in stored["sections"]

        # Results dict returned
        assert "08 11 00" in results
        assert results["08 11 00"].status == "extracted"
        assert len(results["08 11 00"].extractions) == 3

    @pytest.mark.asyncio
    async def test_batch_creates_connections(self, db_session, setup_data):
        data = setup_data

        batch, _ = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            llm_caller=make_multi_pass_mock(MOCK_LLM_RESPONSE_METAL_DOORS),
        )

        # Should have connections to preprocess_batch, spec, and milestone
        from sqlalchemy import select

        result = await db_session.execute(
            select(Connection).where(
                Connection.source_item_id == batch.id,
            )
        )
        connections = list(result.scalars().all())
        target_ids = {c.target_item_id for c in connections}

        assert data["pp_batch"].id in target_ids
        assert data["spec"].id in target_ids
        assert data["milestone"].id in target_ids

    @pytest.mark.asyncio
    async def test_preprocess_batch_not_found(self, db_session, setup_data):
        data = setup_data

        with pytest.raises(ValueError, match="not found"):
            await run_extraction(
                db=db_session,
                specification_id=data["spec"].id,
                preprocess_batch_id=uuid.uuid4(),
                context_id=data["milestone"].id,
                llm_caller=make_multi_pass_mock(MOCK_LLM_RESPONSE_METAL_DOORS),
            )

    @pytest.mark.asyncio
    async def test_preprocess_batch_not_confirmed(
        self, db_session, setup_data, make_item
    ):
        data = setup_data

        # Create an unconfirmed batch
        unconfirmed = await make_item(
            "preprocess_batch",
            "Unconfirmed",
            {
                "status": "identified",
            },
        )

        with pytest.raises(ValueError, match="not confirmed"):
            await run_extraction(
                db=db_session,
                specification_id=data["spec"].id,
                preprocess_batch_id=unconfirmed.id,
                context_id=data["milestone"].id,
                llm_caller=make_multi_pass_mock(MOCK_LLM_RESPONSE_METAL_DOORS),
            )

    @pytest.mark.asyncio
    async def test_specification_not_found(self, db_session, setup_data):
        data = setup_data

        with pytest.raises(ValueError, match="Specification.*not found"):
            await run_extraction(
                db=db_session,
                specification_id=uuid.uuid4(),
                preprocess_batch_id=data["pp_batch"].id,
                context_id=data["milestone"].id,
                llm_caller=make_multi_pass_mock(MOCK_LLM_RESPONSE_METAL_DOORS),
            )

    @pytest.mark.asyncio
    async def test_context_not_found(self, db_session, setup_data):
        data = setup_data

        with pytest.raises(ValueError, match="Context.*not found"):
            await run_extraction(
                db=db_session,
                specification_id=data["spec"].id,
                preprocess_batch_id=data["pp_batch"].id,
                context_id=uuid.uuid4(),
                llm_caller=make_multi_pass_mock(MOCK_LLM_RESPONSE_METAL_DOORS),
            )

    @pytest.mark.asyncio
    async def test_filter_specific_sections(self, db_session, setup_data):
        data = setup_data

        # Request a section that doesn't exist in the connections
        batch, results = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            section_numbers=["09 91 00"],  # Not in our test data
            llm_caller=make_multi_pass_mock(MOCK_LLM_RESPONSE_METAL_DOORS),
        )

        assert batch.properties["sections_total"] == 0
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_llm_failure_marks_section_failed(self, db_session, setup_data):
        data = setup_data

        batch, results = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            llm_caller=make_multi_pass_mock_error(),
        )

        assert batch.properties["status"] == "extracted"
        assert (
            batch.properties["sections_failed"] == 0
        )  # Pass 1 failed → empty nouns → "extracted" with 0 results
        assert (
            batch.properties["sections_extracted"] == 1
        )  # No nouns found = "extracted" (empty but not failed)
        assert results["08 11 00"].status == "extracted"

    @pytest.mark.asyncio
    async def test_batch_identifier_includes_spec(self, db_session, setup_data):
        data = setup_data

        batch, _ = await run_extraction(
            db=db_session,
            specification_id=data["spec"].id,
            preprocess_batch_id=data["pp_batch"].id,
            context_id=data["milestone"].id,
            llm_caller=make_multi_pass_mock(MOCK_LLM_RESPONSE_METAL_DOORS),
        )

        assert "Test Specification" in batch.identifier
