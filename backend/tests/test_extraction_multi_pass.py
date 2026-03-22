"""
Tests for WP-17 v2: Multi-Pass Extraction — Noun Identification,
Per-Noun Extraction, Deterministic Attribution.

Covers:
  - Unit tests: noun identification prompt, parser, per-noun prompt, parser
  - Service tests: identify_nouns, extract_per_noun, attribute_nouns_to_elements,
    extract_section_multi_pass (DB + mock LLM)
  - Frame type registration validation
"""

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.type_config import (
    get_type_config,
    get_vocabulary_for_division,
    get_types_for_division,
)
from app.models.core import Item
from app.services.extraction_service import (
    assemble_vocabulary,
    attribute_nouns_to_elements,
    build_noun_identification_prompt,
    build_per_noun_extraction_prompt,
    build_valid_properties,
    extract_per_noun,
    extract_section_multi_pass,
    identify_nouns,
    parse_noun_identification_response,
    parse_per_noun_extraction_response,
)
from app.schemas.extraction import NounExtraction, NounIdentification


# ═══════════════════════════════════════════════════════════════════
# Test Data
# ═══════════════════════════════════════════════════════════════════

SAMPLE_PART2 = """
PART 2 - PRODUCTS

2.1 METAL DOORS

A. Steel Doors: ANSI/SDI A250.8, Level 3, Model 2, 16 gauge.
   1. Material: Hollow metal, cold-rolled steel.
   2. Finish: Factory applied rust-inhibitive primer.

2.2 METAL FRAMES

A. Hollow Metal Frames: 16 gauge, welded construction.
   1. Material: Galvanized steel.
   2. Fire Rating: UL listed, B-Label.

B. Hardware: Per Section 08 71 00.
"""

SAMPLE_PART1 = """
PART 1 - GENERAL

1.1 RELATED SECTIONS:
    Section 08 71 00 - Door Hardware
"""


# ═══════════════════════════════════════════════════════════════════
# Frame Type Registration Tests
# ═══════════════════════════════════════════════════════════════════


class TestFrameTypeRegistration:
    """Verify the frame type is properly registered (Decision D-25)."""

    def test_frame_type_exists(self):
        tc = get_type_config("frame")
        assert tc is not None
        assert tc.label == "Frame"
        assert tc.category == "spatial"

    def test_frame_in_division_08(self):
        types = get_types_for_division("08")
        assert "frame" in types

    def test_frame_vocabulary(self):
        vocab = get_vocabulary_for_division("08")
        assert "frame" in vocab
        prop_names = {p.name for p in vocab["frame"]}
        assert "material" in prop_names
        assert "gauge" in prop_names
        assert "fire_rating" in prop_names
        assert "finish" in prop_names
        assert "type" in prop_names

    def test_frame_properties_count(self):
        tc = get_type_config("frame")
        assert len(tc.properties) == 5


# ═══════════════════════════════════════════════════════════════════
# Noun Identification Prompt Tests
# ═══════════════════════════════════════════════════════════════════


class TestNounIdentificationPrompt:
    """Test build_noun_identification_prompt."""

    def test_prompt_includes_known_types(self):
        vocab = assemble_vocabulary("08")
        prompt = build_noun_identification_prompt(
            "08 11 00",
            "Metal Doors and Frames",
            SAMPLE_PART2,
            vocab,
        )
        assert "door" in prompt
        assert "frame" in prompt

    def test_prompt_includes_section_text(self):
        vocab = assemble_vocabulary("08")
        prompt = build_noun_identification_prompt(
            "08 11 00",
            "Metal Doors and Frames",
            SAMPLE_PART2,
            vocab,
        )
        assert "Hollow metal" in prompt
        assert "16 gauge" in prompt

    def test_prompt_includes_identification_rules(self):
        vocab = assemble_vocabulary("08")
        prompt = build_noun_identification_prompt(
            "08 11 00",
            None,
            SAMPLE_PART2,
            vocab,
        )
        assert "Identify each distinct product" in prompt
        assert "qualifying attributes" in prompt

    def test_prompt_includes_output_schema(self):
        vocab = assemble_vocabulary("08")
        prompt = build_noun_identification_prompt(
            "08 11 00",
            None,
            SAMPLE_PART2,
            vocab,
        )
        assert '"noun_phrase"' in prompt
        assert '"matched_type"' in prompt
        assert '"qualifiers"' in prompt


# ═══════════════════════════════════════════════════════════════════
# Noun Identification Response Parsing Tests
# ═══════════════════════════════════════════════════════════════════


class TestNounIdentificationParsing:
    """Test parse_noun_identification_response."""

    def _valid_types(self) -> set[str]:
        vocab = assemble_vocabulary("08")
        return set(vocab.get("primary", {}).keys())

    def test_parse_valid_response(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "nouns": [
                    {
                        "noun_phrase": "steel doors",
                        "matched_type": "door",
                        "qualifiers": {"material": "hollow metal"},
                        "context": "Section describes hollow metal steel doors",
                    },
                    {
                        "noun_phrase": "hollow metal frames",
                        "matched_type": "frame",
                        "qualifiers": {"material": "galvanized steel"},
                        "context": "Section describes frames for doors",
                    },
                ],
            }
        )
        result = parse_noun_identification_response(response, self._valid_types())
        assert result.section_number == "08 11 00"
        assert len(result.nouns) == 2
        assert result.nouns[0].noun_phrase == "steel doors"
        assert result.nouns[0].matched_type == "door"
        assert result.nouns[0].qualifiers == {"material": "hollow metal"}

    def test_parse_unknown_type_set_to_none(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "nouns": [
                    {
                        "noun_phrase": "weatherstripping",
                        "matched_type": "weather_seal",
                        "qualifiers": {},
                        "context": "Unknown type",
                    },
                ],
            }
        )
        result = parse_noun_identification_response(response, self._valid_types())
        assert len(result.nouns) == 1
        assert result.nouns[0].matched_type is None  # Invalid type → None

    def test_parse_null_type_preserved(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "nouns": [
                    {
                        "noun_phrase": "hardware sets",
                        "matched_type": None,
                        "qualifiers": {},
                        "context": "Section references hardware",
                    },
                ],
            }
        )
        result = parse_noun_identification_response(response, self._valid_types())
        assert result.nouns[0].matched_type is None

    def test_parse_empty_nouns(self):
        response = json.dumps({"section_number": "08 11 00", "nouns": []})
        result = parse_noun_identification_response(response, self._valid_types())
        assert len(result.nouns) == 0

    def test_parse_invalid_json(self):
        result = parse_noun_identification_response("not json", self._valid_types())
        assert result.section_number == "unknown"
        assert len(result.nouns) == 0

    def test_parse_markdown_fencing(self):
        inner = json.dumps(
            {
                "section_number": "08 11 00",
                "nouns": [
                    {
                        "noun_phrase": "doors",
                        "matched_type": "door",
                        "qualifiers": {},
                        "context": "",
                    }
                ],
            }
        )
        fenced = f"```json\n{inner}\n```"
        result = parse_noun_identification_response(fenced, self._valid_types())
        assert len(result.nouns) == 1

    def test_parse_skips_empty_noun_phrase(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "nouns": [
                    {
                        "noun_phrase": "",
                        "matched_type": "door",
                        "qualifiers": {},
                        "context": "",
                    },
                    {
                        "noun_phrase": "frames",
                        "matched_type": "frame",
                        "qualifiers": {},
                        "context": "",
                    },
                ],
            }
        )
        result = parse_noun_identification_response(response, self._valid_types())
        assert len(result.nouns) == 1
        assert result.nouns[0].noun_phrase == "frames"


# ═══════════════════════════════════════════════════════════════════
# Per-Noun Extraction Prompt Tests
# ═══════════════════════════════════════════════════════════════════


class TestPerNounExtractionPrompt:
    """Test build_per_noun_extraction_prompt."""

    def test_prompt_scoped_to_noun(self):
        vocab = assemble_vocabulary("08")
        prompt = build_per_noun_extraction_prompt(
            "08 11 00",
            "Metal Doors",
            SAMPLE_PART2,
            "steel doors",
            "door",
            vocab,
        )
        assert "steel doors" in prompt
        assert "Focus ONLY on what the section says about" in prompt

    def test_prompt_includes_type_properties(self):
        vocab = assemble_vocabulary("08")
        prompt = build_per_noun_extraction_prompt(
            "08 11 00",
            "Metal Doors",
            SAMPLE_PART2,
            "steel doors",
            "door",
            vocab,
        )
        assert "material" in prompt
        assert "fire_rating" in prompt

    def test_prompt_includes_section_text(self):
        vocab = assemble_vocabulary("08")
        prompt = build_per_noun_extraction_prompt(
            "08 11 00",
            None,
            SAMPLE_PART2,
            "hollow metal frames",
            "frame",
            vocab,
        )
        assert "Galvanized steel" in prompt


# ═══════════════════════════════════════════════════════════════════
# Per-Noun Extraction Response Parsing Tests
# ═══════════════════════════════════════════════════════════════════


class TestPerNounExtractionParsing:
    """Test parse_per_noun_extraction_response."""

    def _valid_props(self) -> dict[str, set[str]]:
        vocab = assemble_vocabulary("08")
        return build_valid_properties(vocab)

    def test_parse_valid_extraction(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "noun_phrase": "steel doors",
                "extractions": [
                    {
                        "property": "material",
                        "element_type": "door",
                        "assertion_type": "flat",
                        "value": "hollow metal",
                        "confidence": 0.95,
                        "source_text": "Material: Hollow metal",
                    },
                ],
                "unrecognized": [],
                "cross_references": [],
            }
        )
        exts, unrec, xrefs = parse_per_noun_extraction_response(
            response,
            "door",
            self._valid_props(),
        )
        assert len(exts) == 1
        assert exts[0].property == "material"
        assert exts[0].value == "hollow metal"

    def test_element_type_fallback_to_matched(self):
        """If LLM returns wrong element_type, fall back to matched_type."""
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "noun_phrase": "frames",
                "extractions": [
                    {
                        "property": "material",
                        "element_type": "FRAME",  # Wrong casing
                        "assertion_type": "flat",
                        "value": "galvanized steel",
                        "confidence": 0.9,
                        "source_text": "Material: Galvanized steel",
                    },
                ],
                "unrecognized": [],
                "cross_references": [],
            }
        )
        exts, _, _ = parse_per_noun_extraction_response(
            response,
            "frame",
            self._valid_props(),
        )
        assert len(exts) == 1
        assert exts[0].element_type == "frame"  # Corrected to matched_type

    def test_invalid_property_skipped(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "extractions": [
                    {
                        "property": "nonexistent",
                        "element_type": "door",
                        "assertion_type": "flat",
                        "value": "x",
                        "confidence": 0.5,
                        "source_text": "...",
                    },
                ],
                "unrecognized": [],
                "cross_references": [],
            }
        )
        exts, _, _ = parse_per_noun_extraction_response(
            response,
            "door",
            self._valid_props(),
        )
        assert len(exts) == 0

    def test_parse_invalid_json(self):
        exts, unrec, xrefs = parse_per_noun_extraction_response(
            "not json",
            "door",
            self._valid_props(),
        )
        assert exts == []
        assert unrec == []
        assert xrefs == []

    def test_parse_with_cross_references(self):
        response = json.dumps(
            {
                "section_number": "08 11 00",
                "extractions": [],
                "unrecognized": [],
                "cross_references": [
                    {
                        "section_number": "08 71 00",
                        "relationship": "hardware",
                        "source_text": "Per Section 08 71 00",
                    },
                ],
            }
        )
        _, _, xrefs = parse_per_noun_extraction_response(
            response,
            "door",
            self._valid_props(),
        )
        assert len(xrefs) == 1
        assert xrefs[0].section_number == "08 71 00"


# ═══════════════════════════════════════════════════════════════════
# Service Tests — identify_nouns
# ═══════════════════════════════════════════════════════════════════


class TestIdentifyNouns:
    """Test identify_nouns async function."""

    @pytest.mark.asyncio
    async def test_identify_nouns_success(self):
        noun_response = json.dumps(
            {
                "section_number": "08 11 00",
                "nouns": [
                    {
                        "noun_phrase": "steel doors",
                        "matched_type": "door",
                        "qualifiers": {},
                        "context": "",
                    },
                    {
                        "noun_phrase": "metal frames",
                        "matched_type": "frame",
                        "qualifiers": {},
                        "context": "",
                    },
                ],
            }
        )

        async def mock_caller(prompt: str) -> str:
            return noun_response

        vocab = assemble_vocabulary("08")
        result = await identify_nouns(
            "08 11 00", "Metal Doors", SAMPLE_PART2, vocab, mock_caller
        )
        assert len(result.nouns) == 2
        assert result.nouns[0].matched_type == "door"
        assert result.nouns[1].matched_type == "frame"

    @pytest.mark.asyncio
    async def test_identify_nouns_llm_error(self):
        async def error_caller(prompt: str) -> str:
            raise RuntimeError("API error")

        vocab = assemble_vocabulary("08")
        result = await identify_nouns(
            "08 11 00", None, SAMPLE_PART2, vocab, error_caller
        )
        assert len(result.nouns) == 0


# ═══════════════════════════════════════════════════════════════════
# Service Tests — extract_per_noun
# ═══════════════════════════════════════════════════════════════════


class TestExtractPerNoun:
    """Test extract_per_noun async function."""

    @pytest.mark.asyncio
    async def test_extract_matched_nouns(self):
        extraction_response = json.dumps(
            {
                "section_number": "08 11 00",
                "noun_phrase": "steel doors",
                "extractions": [
                    {
                        "property": "material",
                        "element_type": "door",
                        "assertion_type": "flat",
                        "value": "hollow metal",
                        "confidence": 0.95,
                        "source_text": "Material: Hollow metal",
                    },
                ],
                "unrecognized": [],
                "cross_references": [],
            }
        )

        async def mock_caller(prompt: str) -> str:
            return extraction_response

        nouns = [
            NounIdentification(
                noun_phrase="steel doors", matched_type="door", qualifiers={}
            ),
        ]
        vocab = assemble_vocabulary("08")

        results = await extract_per_noun(
            "08 11 00", None, SAMPLE_PART2, nouns, vocab, mock_caller
        )
        assert len(results) == 1
        assert len(results[0].extractions) == 1
        assert results[0].extractions[0].property == "material"

    @pytest.mark.asyncio
    async def test_unmatched_noun_skipped(self):
        async def mock_caller(prompt: str) -> str:
            return "{}"  # Should never be called for unmatched

        nouns = [
            NounIdentification(
                noun_phrase="weatherstripping", matched_type=None, qualifiers={}
            ),
        ]
        vocab = assemble_vocabulary("08")

        results = await extract_per_noun(
            "08 11 00", None, SAMPLE_PART2, nouns, vocab, mock_caller
        )
        assert len(results) == 1
        assert results[0].attribution_status == "unmatched_type"
        assert len(results[0].extractions) == 0

    @pytest.mark.asyncio
    async def test_llm_failure_per_noun_graceful(self):
        async def error_caller(prompt: str) -> str:
            raise RuntimeError("API error")

        nouns = [
            NounIdentification(noun_phrase="doors", matched_type="door", qualifiers={}),
        ]
        vocab = assemble_vocabulary("08")

        results = await extract_per_noun(
            "08 11 00", None, SAMPLE_PART2, nouns, vocab, error_caller
        )
        assert len(results) == 1
        assert len(results[0].extractions) == 0  # Graceful failure


# ═══════════════════════════════════════════════════════════════════
# Service Tests — Deterministic Attribution
# ═══════════════════════════════════════════════════════════════════


class TestAttributeNounsToElements:
    """Test attribute_nouns_to_elements with database."""

    @pytest.mark.asyncio
    async def test_matched_type_with_elements(self, db_session, make_item):
        """Nouns matching a type with existing items → 'matched'."""
        door1 = await make_item("door", "D-101", {"material": "hollow metal"})
        door2 = await make_item("door", "D-102", {"material": "wood"})

        nouns = [
            NounExtraction(
                noun_phrase="steel doors", matched_type="door", qualifiers={}
            ),
        ]

        result = await attribute_nouns_to_elements(db_session, nouns)
        assert result[0].attribution_status == "matched"
        assert len(result[0].attributed_elements) == 2  # Both doors

    @pytest.mark.asyncio
    async def test_qualifier_filtering(self, db_session, make_item):
        """Qualifiers narrow attribution to matching items."""
        await make_item("door", "D-101", {"material": "hollow metal"})
        await make_item("door", "D-102", {"material": "wood"})

        nouns = [
            NounExtraction(
                noun_phrase="hollow metal doors",
                matched_type="door",
                qualifiers={"material": "hollow metal"},
            ),
        ]

        result = await attribute_nouns_to_elements(db_session, nouns)
        assert result[0].attribution_status == "matched"
        assert len(result[0].attributed_elements) == 1  # Only D-101

    @pytest.mark.asyncio
    async def test_no_elements_discovered_entity(self, db_session):
        """Known type but no items → 'no_elements' (Decision D-24)."""
        nouns = [
            NounExtraction(noun_phrase="frames", matched_type="frame", qualifiers={}),
        ]

        result = await attribute_nouns_to_elements(db_session, nouns)
        assert result[0].attribution_status == "no_elements"
        assert len(result[0].attributed_elements) == 0

    @pytest.mark.asyncio
    async def test_unmatched_type(self, db_session):
        """Noun with no matched_type → 'unmatched_type'."""
        nouns = [
            NounExtraction(
                noun_phrase="weatherstripping", matched_type=None, qualifiers={}
            ),
        ]

        result = await attribute_nouns_to_elements(db_session, nouns)
        assert result[0].attribution_status == "unmatched_type"

    @pytest.mark.asyncio
    async def test_qualifier_narrows_to_zero_falls_back(self, db_session, make_item):
        """If qualifiers narrow to zero, bind to all items of that type."""
        await make_item("door", "D-101", {"material": "wood"})
        await make_item("door", "D-102", {"material": "fiberglass"})

        nouns = [
            NounExtraction(
                noun_phrase="steel doors",
                matched_type="door",
                qualifiers={"material": "steel"},  # No match
            ),
        ]

        result = await attribute_nouns_to_elements(db_session, nouns)
        assert result[0].attribution_status == "matched"
        assert len(result[0].attributed_elements) == 2  # Fell back to all


# ═══════════════════════════════════════════════════════════════════
# Service Tests — Multi-Pass Orchestration
# ═══════════════════════════════════════════════════════════════════


class TestExtractSectionMultiPass:
    """Test extract_section_multi_pass end-to-end."""

    @pytest.mark.asyncio
    async def test_full_multi_pass_pipeline(self, db_session, make_item):
        """Pass 1 → Pass 2 → Attribution in a single call."""
        # Create door items for attribution
        await make_item("door", "D-101", {"material": "hollow metal"})

        noun_response = json.dumps(
            {
                "section_number": "08 11 00",
                "nouns": [
                    {
                        "noun_phrase": "steel doors",
                        "matched_type": "door",
                        "qualifiers": {},
                        "context": "",
                    },
                ],
            }
        )
        extraction_response = json.dumps(
            {
                "section_number": "08 11 00",
                "noun_phrase": "steel doors",
                "extractions": [
                    {
                        "property": "material",
                        "element_type": "door",
                        "assertion_type": "flat",
                        "value": "hollow metal",
                        "confidence": 0.95,
                        "source_text": "Material: Hollow metal",
                    },
                ],
                "unrecognized": [
                    {
                        "term": "STC",
                        "value": "45",
                        "context": "acoustic",
                        "source_text": "STC 45",
                    },
                ],
                "cross_references": [
                    {
                        "section_number": "08 71 00",
                        "relationship": "hardware",
                        "source_text": "Per 08 71 00",
                    },
                ],
            }
        )

        call_count = 0

        async def mock_caller(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if "products, assemblies, components" in prompt.lower():
                return noun_response
            return extraction_response

        result = await extract_section_multi_pass(
            db=db_session,
            section_number="08 11 00",
            section_title="Metal Doors",
            part2_text=SAMPLE_PART2,
            part1_text=SAMPLE_PART1,
            section_division="08",
            llm_caller=mock_caller,
        )

        assert result.status == "extracted"
        assert call_count == 2  # Pass 1 + Pass 2

        # Noun-level results
        assert len(result.nouns) == 1
        assert result.nouns[0].noun_phrase == "steel doors"
        assert result.nouns[0].attribution_status == "matched"
        assert len(result.nouns[0].attributed_elements) == 1

        # Aggregated flat lists (backward compatibility)
        assert len(result.extractions) == 1
        assert result.extractions[0].property == "material"
        assert len(result.unrecognized) == 1
        assert len(result.cross_references) == 1

        # Pass 1 audit trail
        assert result.pass1_response is not None
        assert len(result.pass1_response["nouns"]) == 1

    @pytest.mark.asyncio
    async def test_no_vocabulary_returns_failed(self, db_session):
        async def mock_caller(prompt: str) -> str:
            return "{}"

        result = await extract_section_multi_pass(
            db=db_session,
            section_number="99 00 00",
            section_title=None,
            part2_text="Some text",
            part1_text=None,
            section_division="99",
            llm_caller=mock_caller,
        )
        assert result.status == "failed"
        assert "No element types" in result.error

    @pytest.mark.asyncio
    async def test_empty_part2_returns_failed(self, db_session):
        async def mock_caller(prompt: str) -> str:
            return "{}"

        result = await extract_section_multi_pass(
            db=db_session,
            section_number="08 11 00",
            section_title=None,
            part2_text="",
            part1_text=None,
            section_division="08",
            llm_caller=mock_caller,
        )
        assert result.status == "failed"
        assert "No Part 2" in result.error

    @pytest.mark.asyncio
    async def test_no_nouns_identified(self, db_session):
        """If Pass 1 finds no nouns, return empty but not failed."""

        async def mock_caller(prompt: str) -> str:
            return json.dumps({"section_number": "08 11 00", "nouns": []})

        result = await extract_section_multi_pass(
            db=db_session,
            section_number="08 11 00",
            section_title=None,
            part2_text=SAMPLE_PART2,
            part1_text=None,
            section_division="08",
            llm_caller=mock_caller,
        )
        assert result.status == "extracted"
        assert len(result.nouns) == 0
        assert len(result.extractions) == 0

    @pytest.mark.asyncio
    async def test_cross_reference_deduplication(self, db_session):
        """Same cross-reference from multiple nouns should be deduplicated."""
        noun_response = json.dumps(
            {
                "section_number": "08 11 00",
                "nouns": [
                    {
                        "noun_phrase": "doors",
                        "matched_type": "door",
                        "qualifiers": {},
                        "context": "",
                    },
                    {
                        "noun_phrase": "frames",
                        "matched_type": "frame",
                        "qualifiers": {},
                        "context": "",
                    },
                ],
            }
        )
        extraction_response = json.dumps(
            {
                "section_number": "08 11 00",
                "extractions": [],
                "unrecognized": [],
                "cross_references": [
                    {
                        "section_number": "08 71 00",
                        "relationship": "hardware",
                        "source_text": "Per 08 71 00",
                    },
                ],
            }
        )

        async def mock_caller(prompt: str) -> str:
            if "products, assemblies, components" in prompt.lower():
                return noun_response
            return extraction_response

        result = await extract_section_multi_pass(
            db=db_session,
            section_number="08 11 00",
            section_title=None,
            part2_text=SAMPLE_PART2,
            part1_text=None,
            section_division="08",
            llm_caller=mock_caller,
        )

        # Each noun returns the same cross-ref, but it should be deduplicated
        assert len(result.cross_references) == 1
