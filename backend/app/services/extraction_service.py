"""
Specification Extraction Service — WP-17 (Revised: Multi-Pass).

Extracts property values from preprocessed specification sections using
vocabulary-bounded LLM calls. The vocabulary comes from type_config.py,
not from prior schedule imports (Decision D-11).

Revised Pipeline (v2, Decision D-22):
  1. Retrieve confirmed sections from WP-16 preprocess batch
  2. Pass 1: Noun identification — LLM identifies subjects in each section
  3. Pass 2: Per-noun extraction — LLM extracts properties per identified noun
  4. Deterministic attribution — match nouns to graph elements via type + qualifiers
  5. Store results on extraction_batch item for user confirmation

All LLM interaction is abstracted via LLMCaller for testability.
"""

import json
import logging
import re
import uuid
from typing import Any, Callable, Awaitable

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.type_config import (
    PropertyDef,
    get_type_config,
    get_vocabulary_for_division,
)
from app.models.core import Connection, Item
from app.schemas.extraction import (
    ConditionalAssertion,
    CrossReferenceItem,
    ExtractionItem,
    NounExtraction,
    NounIdentification,
    SectionExtraction,
    SectionNouns,
    UnrecognizedItem,
)

logger = logging.getLogger(__name__)


# ─── LLM Caller Abstraction ─────────────────────────────────────

LLMCaller = Callable[[str], Awaitable[str]]


async def _default_extraction_caller(prompt: str) -> str:
    """Call Anthropic API for property extraction."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=settings.EXTRACTION_MODEL,
        max_tokens=settings.EXTRACTION_MAX_TOKENS,
        temperature=settings.EXTRACTION_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ─── Related Sections Parsing ────────────────────────────────────

RELATED_SECTIONS_PATTERN = re.compile(
    r"(?im)(?:related\s+(?:sections?|requirements?|work)|"
    r"see\s+also|reference\s+sections?)\s*[:.]?\s*\n"
    r"((?:.*\d{2}\s+\d{2}\s+\d{2}.*\n?)+)",
)

SECTION_NUMBER_EXTRACT = re.compile(r"(\d{2})\s+\d{2}\s+\d{2}")


def parse_related_sections(part1_text: str | None) -> list[str]:
    """
    Extract division codes from Related Sections in Part 1 text.

    Looks for patterns like:
      RELATED SECTIONS:
        Section 08 71 00 - Door Hardware
        Section 09 91 00 - Painting

    Args:
        part1_text: Part 1 text from WP-16 preprocessing. May be None.

    Returns:
        List of unique two-digit division codes (e.g., ["08", "09"]).
    """
    if not part1_text:
        return []

    divisions: set[str] = set()
    for match in RELATED_SECTIONS_PATTERN.finditer(part1_text):
        block = match.group(1)
        for num_match in SECTION_NUMBER_EXTRACT.finditer(block):
            divisions.add(num_match.group(1))

    return sorted(divisions)


# ─── Vocabulary Assembly ─────────────────────────────────────────


def assemble_vocabulary(
    section_division: str,
    related_divisions: list[str] | None = None,
) -> dict[str, dict[str, list[PropertyDef]]]:
    """
    Assemble the extraction vocabulary for a spec section.

    Returns a dict with "primary" and "secondary" vocabulary, each
    mapping type_name → list of PropertyDef.

    Primary vocabulary: types governed by this section's division.
    Secondary vocabulary: types from related sections' divisions
    (excluding types already in primary).

    Args:
        section_division: Two-digit MasterFormat division (e.g., "08").
        related_divisions: Division codes from Related Sections in Part 1.

    Returns:
        {"primary": {type: [PropertyDef, ...]},
         "secondary": {type: [PropertyDef, ...]}}
    """
    primary = get_vocabulary_for_division(section_division)

    secondary: dict[str, list[PropertyDef]] = {}
    if related_divisions:
        for div in related_divisions:
            if div == section_division:
                continue  # Already in primary
            for type_name, props in get_vocabulary_for_division(div).items():
                if type_name not in primary and type_name not in secondary:
                    secondary[type_name] = props

    return {"primary": primary, "secondary": secondary}


# ─── Prompt Construction ─────────────────────────────────────────


def _format_property_list(
    type_name: str,
    properties: list[PropertyDef],
) -> str:
    """Format a PropertyDef list for inclusion in the extraction prompt."""
    lines = []
    for prop in properties:
        parts = [f"- {prop.name} ({prop.data_type}): {prop.description or prop.label}"]
        if prop.enum_values:
            parts.append(f"  Allowed values: {', '.join(prop.enum_values)}")
        if prop.unit:
            parts.append(f"  Unit: {prop.unit}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


def build_extraction_prompt(
    section_number: str,
    section_title: str | None,
    part2_text: str,
    vocabulary: dict[str, dict[str, list[PropertyDef]]],
) -> str:
    """
    Build the extraction prompt for a single spec section (v1 single-pass).

    Retained for backward compatibility. The multi-pass pipeline uses
    build_noun_identification_prompt() and build_per_noun_extraction_prompt().

    Args:
        section_number: MasterFormat section number (e.g., "08 11 00").
        section_title: Section title if known (e.g., "Metal Doors and Frames").
        part2_text: Part 2 (Products) text from WP-16 preprocessing.
        vocabulary: Output of assemble_vocabulary().

    Returns:
        Complete prompt string for the LLM.
    """
    # Build property sections
    prop_sections = []

    for type_name, props in vocabulary.get("primary", {}).items():
        tc = get_type_config(type_name)
        type_label = tc.label if tc else type_name
        prop_sections.append(
            f"### {type_label} properties (primary)\n"
            f"{_format_property_list(type_name, props)}"
        )

    for type_name, props in vocabulary.get("secondary", {}).items():
        tc = get_type_config(type_name)
        type_label = tc.label if tc else type_name
        prop_sections.append(
            f"### {type_label} properties (from related sections)\n"
            f"{_format_property_list(type_name, props)}"
        )

    properties_block = (
        "\n\n".join(prop_sections) if prop_sections else "No target properties defined."
    )

    # Build the list of all type names for the output schema
    all_types = []
    for group in ("primary", "secondary"):
        all_types.extend(vocabulary.get(group, {}).keys())

    title_display = f" — {section_title}" if section_title else ""

    prompt = f"""You are extracting property values from a construction specification section.
You will receive the section text and a list of target properties with descriptions.
Your job is to find explicit assertions about each property in the text.

Rules:
- Only extract values that are explicitly stated in the text.
- Do not infer, assume, or generate values not directly asserted.
- For each extracted value, cite the exact clause or sentence it comes from.
- If a property is not mentioned in the text, do NOT include it in the output.
- If a property has conditional assertions (e.g., "if X then Y"), use assertion_type "conditional" and report each condition and value separately.
- Report any material or performance requirements you find that do not match any of the target properties listed below.
- Report any cross-references to other specification sections (e.g., "per Section 08 71 00").

## Specification Section
Section: {section_number}{title_display}

## Section Text
{part2_text}

## Target Properties

{properties_block}

## Output Format
Respond with JSON only. No markdown fencing, no explanation.

{{
  "section_number": "{section_number}",
  "extractions": [
    {{
      "property": "<property_name>",
      "element_type": "<type_name from: {", ".join(all_types) if all_types else "unknown"}>",
      "assertion_type": "flat",
      "value": "<extracted value>",
      "confidence": <0.0-1.0>,
      "source_text": "<exact clause>"
    }},
    {{
      "property": "<property_name>",
      "element_type": "<type_name>",
      "assertion_type": "conditional",
      "assertions": [
        {{"value": "<value>", "condition": "<condition>", "source_text": "<exact clause>"}}
      ],
      "confidence": <0.0-1.0>
    }}
  ],
  "unrecognized": [
    {{
      "term": "<requirement name>",
      "value": "<extracted value>",
      "context": "<what type of requirement>",
      "source_text": "<exact clause>"
    }}
  ],
  "cross_references": [
    {{
      "section_number": "<XX XX XX>",
      "relationship": "<what the reference is about>",
      "source_text": "<exact clause>"
    }}
  ]
}}"""

    return prompt


# ─── Pass 1: Noun Identification ────────────────────────────────


def build_noun_identification_prompt(
    section_number: str,
    section_title: str | None,
    part2_text: str,
    vocabulary: dict[str, dict[str, list[PropertyDef]]],
) -> str:
    """
    Build the Pass 1 prompt: identify subjects (nouns) in a spec section.

    Per WP-17v2 §A1.3, the LLM reads the section text and identifies
    the products, assemblies, or components the section discusses.

    Args:
        section_number: MasterFormat section number.
        section_title: Section title if known.
        part2_text: Part 2 text from WP-16.
        vocabulary: Output of assemble_vocabulary().

    Returns:
        Complete Pass 1 prompt string.
    """
    # Build known element types list
    type_lines = []
    for group in ("primary", "secondary"):
        for type_name, props in vocabulary.get(group, {}).items():
            tc = get_type_config(type_name)
            type_label = tc.label if tc else type_name
            prop_names = ", ".join(p.name for p in props[:8])  # First 8 for context
            type_lines.append(f"- {type_name} ({type_label}): {prop_names}")

    known_types_block = "\n".join(type_lines) if type_lines else "No known types."

    title_display = f" — {section_title}" if section_title else ""

    prompt = f"""You are analyzing a construction specification section to identify what things
(products, assemblies, components) it describes.

Rules:
- Identify each distinct product, assembly, or component the section discusses.
- For each item, provide its name as used in the spec text.
- Match each item to one of the known element types listed below if possible.
- For each matched item, identify any qualifying attributes that distinguish it
  from other items of the same type (e.g., material, size, rating).
- If an item doesn't match any known type, report it as unmatched.
- Do not infer items that are not explicitly discussed in the section text.

## Known Element Types
{known_types_block}

## Specification Section
Section: {section_number}{title_display}

## Section Text
{part2_text}

## Output Format
Respond with JSON only. No markdown fencing, no explanation.

{{
  "section_number": "{section_number}",
  "nouns": [
    {{
      "noun_phrase": "<name as used in spec text>",
      "matched_type": "<type_name from known types, or null>",
      "qualifiers": {{"<property>": "<value>"}},
      "context": "<brief description of what the spec says about this item>"
    }}
  ]
}}"""

    return prompt


def parse_noun_identification_response(
    response_text: str,
    valid_types: set[str],
) -> SectionNouns:
    """
    Parse the Pass 1 LLM response into a SectionNouns.

    Validates matched_type against known types. Nouns with invalid
    matched_type are set to None (unmatched) rather than discarded.

    Args:
        response_text: Raw LLM response text.
        valid_types: Set of valid type names from vocabulary.

    Returns:
        SectionNouns with parsed noun identifications.
    """
    text = _strip_markdown_fencing(response_text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse noun identification response: {e}")
        return SectionNouns(section_number="unknown")

    if not isinstance(parsed, dict):
        logger.error(f"Noun identification response is not a dict: {type(parsed)}")
        return SectionNouns(section_number="unknown")

    section_number = str(parsed.get("section_number", "unknown"))
    nouns: list[NounIdentification] = []

    for entry in parsed.get("nouns", []):
        try:
            noun_phrase = str(entry.get("noun_phrase", "")).strip()
            if not noun_phrase:
                continue

            matched_type = entry.get("matched_type")
            if matched_type is not None:
                matched_type = str(matched_type).strip()
                if matched_type not in valid_types:
                    logger.warning(
                        f"Noun '{noun_phrase}' matched to unknown type "
                        f"'{matched_type}', setting to None"
                    )
                    matched_type = None

            qualifiers = {}
            raw_quals = entry.get("qualifiers", {})
            if isinstance(raw_quals, dict):
                qualifiers = {str(k): str(v) for k, v in raw_quals.items()}

            context = str(entry.get("context", ""))

            nouns.append(
                NounIdentification(
                    noun_phrase=noun_phrase,
                    matched_type=matched_type,
                    qualifiers=qualifiers,
                    context=context,
                )
            )

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Skipping malformed noun entry: {e}")
            continue

    return SectionNouns(section_number=section_number, nouns=nouns)


# ─── Pass 2: Per-Noun Extraction ────────────────────────────────


def build_per_noun_extraction_prompt(
    section_number: str,
    section_title: str | None,
    part2_text: str,
    noun_phrase: str,
    matched_type: str,
    vocabulary: dict[str, dict[str, list[PropertyDef]]],
) -> str:
    """
    Build the Pass 2 prompt: extract properties for a specific noun.

    Per WP-17v2 §A1.4, the prompt is scoped to what the section says
    about a specific identified subject.

    Args:
        section_number: MasterFormat section number.
        section_title: Section title if known.
        part2_text: Part 2 text.
        noun_phrase: The specific noun to extract for.
        matched_type: The type_config type this noun matched to.
        vocabulary: Output of assemble_vocabulary().

    Returns:
        Complete Pass 2 prompt string for this noun.
    """
    # Get properties for the matched type
    type_props = None
    for group in ("primary", "secondary"):
        group_vocab = vocabulary.get(group, {})
        if matched_type in group_vocab:
            type_props = group_vocab[matched_type]
            break

    if type_props:
        props_block = _format_property_list(matched_type, type_props)
    else:
        props_block = "No target properties defined for this type."

    title_display = f" — {section_title}" if section_title else ""

    prompt = f"""You are extracting property values from a construction specification section.
Focus ONLY on what the section says about: {noun_phrase}

Rules:
- Only extract values that are explicitly stated about {noun_phrase}.
- Do not extract values that apply to other items in the section.
- Do not infer, assume, or generate values not directly asserted.
- For each extracted value, cite the exact clause or sentence it comes from.
- If a property has conditional assertions (e.g., "if X then Y"), use
  assertion_type "conditional" and report each condition and value separately.
- Report any requirements you find that do not match the target properties below.
- Report any cross-references to other specification sections.

## Specification Section
Section: {section_number}{title_display}
Subject: {noun_phrase} (type: {matched_type})

## Section Text
{part2_text}

## Target Properties for {matched_type}
{props_block}

## Output Format
Respond with JSON only. No markdown fencing, no explanation.

{{
  "section_number": "{section_number}",
  "noun_phrase": "{noun_phrase}",
  "extractions": [
    {{
      "property": "<property_name>",
      "element_type": "{matched_type}",
      "assertion_type": "flat",
      "value": "<extracted value>",
      "confidence": <0.0-1.0>,
      "source_text": "<exact clause>"
    }},
    {{
      "property": "<property_name>",
      "element_type": "{matched_type}",
      "assertion_type": "conditional",
      "assertions": [
        {{"value": "<value>", "condition": "<condition>", "source_text": "<exact clause>"}}
      ],
      "confidence": <0.0-1.0>
    }}
  ],
  "unrecognized": [
    {{
      "term": "<requirement name>",
      "value": "<extracted value>",
      "context": "<what type of requirement>",
      "source_text": "<exact clause>"
    }}
  ],
  "cross_references": [
    {{
      "section_number": "<XX XX XX>",
      "relationship": "<what the reference is about>",
      "source_text": "<exact clause>"
    }}
  ]
}}"""

    return prompt


def parse_per_noun_extraction_response(
    response_text: str,
    matched_type: str,
    valid_properties: dict[str, set[str]],
) -> tuple[list[ExtractionItem], list[UnrecognizedItem], list[CrossReferenceItem]]:
    """
    Parse a Pass 2 per-noun LLM response.

    Uses the same parsing logic as v1 parse_extraction_response but
    returns individual lists rather than a SectionExtraction.

    Args:
        response_text: Raw LLM response text.
        matched_type: The type this noun was matched to.
        valid_properties: Dict mapping type_name → set of valid property names.

    Returns:
        Tuple of (extractions, unrecognized, cross_references) for this noun.
    """
    text = _strip_markdown_fencing(response_text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse per-noun extraction response: {e}")
        return [], [], []

    if not isinstance(parsed, dict):
        logger.error(f"Per-noun extraction response is not a dict: {type(parsed)}")
        return [], [], []

    extractions: list[ExtractionItem] = []
    unrecognized: list[UnrecognizedItem] = []
    cross_references: list[CrossReferenceItem] = []

    valid_types = set(valid_properties.keys())

    for entry in parsed.get("extractions", []):
        try:
            prop_name = str(entry.get("property", "")).strip()
            element_type = str(entry.get("element_type", "")).strip()
            assertion_type = str(entry.get("assertion_type", "flat")).strip()

            # Validate element type — accept matched_type even if LLM uses different casing
            if element_type not in valid_types:
                # Try the matched_type as fallback
                if matched_type in valid_types:
                    element_type = matched_type
                else:
                    logger.warning(
                        f"Per-noun extraction references unknown type '{element_type}', skipping"
                    )
                    continue

            # Validate property name
            if prop_name not in valid_properties.get(element_type, set()):
                logger.warning(
                    f"Per-noun extraction references unknown property '{prop_name}' "
                    f"on type '{element_type}', skipping"
                )
                continue

            if assertion_type not in ("flat", "conditional"):
                assertion_type = "flat"

            if assertion_type == "conditional":
                raw_assertions = entry.get("assertions", [])
                cond_assertions = []
                for a in raw_assertions:
                    cond_assertions.append(
                        ConditionalAssertion(
                            value=str(a.get("value", "")),
                            condition=str(a.get("condition", "")),
                            source_text=str(a.get("source_text", "")),
                        )
                    )
                extractions.append(
                    ExtractionItem(
                        property=prop_name,
                        element_type=element_type,
                        assertion_type="conditional",
                        assertions=cond_assertions,
                        confidence=float(entry.get("confidence", 0.0)),
                        source_text=str(entry.get("source_text", "")),
                    )
                )
            else:
                extractions.append(
                    ExtractionItem(
                        property=prop_name,
                        element_type=element_type,
                        assertion_type="flat",
                        value=str(entry.get("value", "")),
                        confidence=float(entry.get("confidence", 0.0)),
                        source_text=str(entry.get("source_text", "")),
                    )
                )
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Skipping malformed per-noun extraction entry: {e}")
            continue

    for entry in parsed.get("unrecognized", []):
        try:
            unrecognized.append(
                UnrecognizedItem(
                    term=str(entry.get("term", "")),
                    value=str(entry.get("value", "")),
                    context=str(entry.get("context", "")),
                    source_text=str(entry.get("source_text", "")),
                )
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed unrecognized entry: {e}")
            continue

    for entry in parsed.get("cross_references", []):
        try:
            cross_references.append(
                CrossReferenceItem(
                    section_number=str(entry.get("section_number", "")),
                    relationship=str(entry.get("relationship", "")),
                    source_text=str(entry.get("source_text", "")),
                )
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed cross-reference entry: {e}")
            continue

    return extractions, unrecognized, cross_references


# ─── Deterministic Attribution ──────────────────────────────────


async def attribute_nouns_to_elements(
    db: AsyncSession,
    nouns: list[NounExtraction],
) -> list[NounExtraction]:
    """
    Deterministic element attribution: match nouns to graph items.

    For each noun with a matched_type, query the graph for items of that
    type. Apply qualifier-based filtering when possible.

    Decision D-23: Attribution is deterministic (no LLM). Type + qualifiers
    → SQL query. Attribution results are:
      - "matched": Elements found and bound to this noun.
      - "no_elements": Known type but no items exist (discovered entity, D-24).
      - "unmatched_type": Noun didn't match any known type.

    Args:
        db: Async database session.
        nouns: List of NounExtraction objects with matched_type set.

    Returns:
        Updated list of NounExtraction with attribution_status and
        attributed_elements populated.
    """
    for noun in nouns:
        if noun.matched_type is None:
            noun.attribution_status = "unmatched_type"
            continue

        # Query for items of the matched type
        query = select(Item).where(Item.item_type == noun.matched_type)
        result = await db.execute(query)
        candidates = result.scalars().all()

        if not candidates:
            noun.attribution_status = "no_elements"
            continue

        # Apply qualifier-based filtering
        if noun.qualifiers:
            matched = []
            for item in candidates:
                item_props = item.properties or {}
                qualifies = True
                for qual_key, qual_value in noun.qualifiers.items():
                    item_value = item_props.get(qual_key, "")
                    # Case-insensitive substring match for qualifiers
                    if qual_value.lower() not in str(item_value).lower():
                        qualifies = False
                        break
                if qualifies:
                    matched.append(str(item.id))

            if matched:
                noun.attributed_elements = matched
                noun.attribution_status = "matched"
            else:
                # Qualifiers narrowed to zero — still bind to all of that type
                # (user will refine during confirmation)
                noun.attributed_elements = [str(item.id) for item in candidates]
                noun.attribution_status = "matched"
        else:
            # No qualifiers — bind to all items of this type
            noun.attributed_elements = [str(item.id) for item in candidates]
            noun.attribution_status = "matched"

    return nouns


# ─── Response Parsing (v1 — retained for backward compatibility) ─


def _strip_markdown_fencing(text: str) -> str:
    """Remove markdown code fences from LLM response if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def parse_extraction_response(
    response_text: str,
    valid_properties: dict[str, set[str]],
) -> SectionExtraction:
    """
    Parse the LLM's JSON response into a SectionExtraction (v1 single-pass).

    Validates property names and element types against the vocabulary
    that was sent in the prompt. Invalid entries are logged and skipped.

    Retained for backward compatibility with v1 tests and single-pass mode.

    Args:
        response_text: Raw LLM response text.
        valid_properties: Dict mapping type_name → set of valid property names.
                         Built from the vocabulary sent in the prompt.

    Returns:
        SectionExtraction with parsed extractions, unrecognized terms,
        and cross-references.
    """
    text = _strip_markdown_fencing(response_text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse extraction response: {e}. Text: {text[:300]}")
        return SectionExtraction(
            section_number="unknown",
            status="failed",
            error=f"Invalid JSON response: {e}",
        )

    if not isinstance(parsed, dict):
        logger.error(f"Extraction response is not a dict: {type(parsed)}")
        return SectionExtraction(
            section_number="unknown",
            status="failed",
            error="Response is not a JSON object",
        )

    section_number = str(parsed.get("section_number", "unknown"))
    extractions: list[ExtractionItem] = []
    unrecognized: list[UnrecognizedItem] = []
    cross_references: list[CrossReferenceItem] = []

    # Valid types are all keys in valid_properties
    valid_types = set(valid_properties.keys())

    # Parse extractions
    for entry in parsed.get("extractions", []):
        try:
            prop_name = str(entry.get("property", "")).strip()
            element_type = str(entry.get("element_type", "")).strip()
            assertion_type = str(entry.get("assertion_type", "flat")).strip()

            # Validate element type
            if element_type not in valid_types:
                logger.warning(
                    f"Extraction references unknown type '{element_type}', skipping"
                )
                continue

            # Validate property name
            if prop_name not in valid_properties.get(element_type, set()):
                logger.warning(
                    f"Extraction references unknown property '{prop_name}' "
                    f"on type '{element_type}', skipping"
                )
                continue

            # Validate assertion type
            if assertion_type not in ("flat", "conditional"):
                assertion_type = "flat"

            if assertion_type == "conditional":
                raw_assertions = entry.get("assertions", [])
                cond_assertions = []
                for a in raw_assertions:
                    cond_assertions.append(
                        ConditionalAssertion(
                            value=str(a.get("value", "")),
                            condition=str(a.get("condition", "")),
                            source_text=str(a.get("source_text", "")),
                        )
                    )

                extractions.append(
                    ExtractionItem(
                        property=prop_name,
                        element_type=element_type,
                        assertion_type="conditional",
                        assertions=cond_assertions,
                        confidence=float(entry.get("confidence", 0.0)),
                        source_text=str(entry.get("source_text", "")),
                    )
                )
            else:
                extractions.append(
                    ExtractionItem(
                        property=prop_name,
                        element_type=element_type,
                        assertion_type="flat",
                        value=str(entry.get("value", "")),
                        confidence=float(entry.get("confidence", 0.0)),
                        source_text=str(entry.get("source_text", "")),
                    )
                )

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Skipping malformed extraction entry: {e}")
            continue

    # Parse unrecognized terms
    for entry in parsed.get("unrecognized", []):
        try:
            unrecognized.append(
                UnrecognizedItem(
                    term=str(entry.get("term", "")),
                    value=str(entry.get("value", "")),
                    context=str(entry.get("context", "")),
                    source_text=str(entry.get("source_text", "")),
                )
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed unrecognized entry: {e}")
            continue

    # Parse cross-references
    for entry in parsed.get("cross_references", []):
        try:
            cross_references.append(
                CrossReferenceItem(
                    section_number=str(entry.get("section_number", "")),
                    relationship=str(entry.get("relationship", "")),
                    source_text=str(entry.get("source_text", "")),
                )
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed cross-reference entry: {e}")
            continue

    status = (
        "extracted" if extractions or unrecognized or cross_references else "extracted"
    )

    return SectionExtraction(
        section_number=section_number,
        status=status,
        extractions=extractions,
        unrecognized=unrecognized,
        cross_references=cross_references,
    )


def build_valid_properties(
    vocabulary: dict[str, dict[str, list[PropertyDef]]],
) -> dict[str, set[str]]:
    """
    Build a validation map from the vocabulary sent to the LLM.

    Returns dict mapping type_name → set of valid property names.
    """
    result: dict[str, set[str]] = {}
    for group in ("primary", "secondary"):
        for type_name, props in vocabulary.get(group, {}).items():
            if type_name not in result:
                result[type_name] = set()
            result[type_name].update(p.name for p in props)
    return result


# ─── Section-Level Extraction (v1 — retained) ──────────────────


async def extract_section(
    section_number: str,
    section_title: str | None,
    part2_text: str,
    part1_text: str | None,
    section_division: str,
    llm_caller: LLMCaller,
    vocabulary: dict[str, dict[str, list[PropertyDef]]] | None = None,
) -> SectionExtraction:
    """
    Extract properties from a single spec section (v1 single-pass).

    Assembles vocabulary, builds prompt, calls LLM, parses response.
    Retained for backward compatibility. New code should use
    extract_section_multi_pass().

    Args:
        section_number: MasterFormat section number (e.g., "08 11 00").
        section_title: Section title if known.
        part2_text: Part 2 text from WP-16.
        part1_text: Part 1 text (for Related Sections parsing). May be None.
        section_division: Two-digit division code (e.g., "08").
        llm_caller: Callable for LLM invocation.

    Returns:
        SectionExtraction with results.
    """
    if not part2_text or not part2_text.strip():
        return SectionExtraction(
            section_number=section_number,
            status="failed",
            error="No Part 2 text available for extraction",
        )

    # Assemble vocabulary (use provided vocabulary if given, e.g., from firm types)
    if vocabulary is None:
        related_divs = parse_related_sections(part1_text)
        vocabulary = assemble_vocabulary(section_division, related_divs)

    # Check we have at least some vocabulary
    has_vocab = bool(vocabulary.get("primary")) or bool(vocabulary.get("secondary"))
    if not has_vocab:
        return SectionExtraction(
            section_number=section_number,
            status="failed",
            error=f"No element types configured for Division {section_division}",
        )

    # Build prompt
    prompt = build_extraction_prompt(
        section_number=section_number,
        section_title=section_title,
        part2_text=part2_text,
        vocabulary=vocabulary,
    )

    # Call LLM
    try:
        response_text = await llm_caller(prompt)
    except Exception as e:
        logger.error(f"LLM extraction failed for {section_number}: {e}")
        return SectionExtraction(
            section_number=section_number,
            status="failed",
            error=f"LLM call failed: {e}",
        )

    # Parse response
    valid_props = build_valid_properties(vocabulary)
    result = parse_extraction_response(response_text, valid_props)
    result.section_number = section_number

    return result


# ─── Multi-Pass Section Extraction (v2) ─────────────────────────


async def identify_nouns(
    section_number: str,
    section_title: str | None,
    part2_text: str,
    vocabulary: dict[str, dict[str, list[PropertyDef]]],
    llm_caller: LLMCaller,
) -> SectionNouns:
    """
    Pass 1: Identify nouns (subjects) in a spec section.

    Calls the LLM with the noun identification prompt, parses the
    response into NounIdentification objects.

    Args:
        section_number: MasterFormat section number.
        section_title: Section title if known.
        part2_text: Part 2 text.
        vocabulary: Output of assemble_vocabulary().
        llm_caller: Callable for LLM invocation.

    Returns:
        SectionNouns with identified nouns.
    """
    prompt = build_noun_identification_prompt(
        section_number=section_number,
        section_title=section_title,
        part2_text=part2_text,
        vocabulary=vocabulary,
    )

    try:
        response_text = await llm_caller(prompt)
    except Exception as e:
        logger.error(f"LLM noun identification failed for {section_number}: {e}")
        return SectionNouns(section_number=section_number)

    # Build set of valid types from vocabulary
    valid_types: set[str] = set()
    for group in ("primary", "secondary"):
        valid_types.update(vocabulary.get(group, {}).keys())

    return parse_noun_identification_response(response_text, valid_types)


async def extract_per_noun(
    section_number: str,
    section_title: str | None,
    part2_text: str,
    nouns: list[NounIdentification],
    vocabulary: dict[str, dict[str, list[PropertyDef]]],
    llm_caller: LLMCaller,
) -> list[NounExtraction]:
    """
    Pass 2: Extract properties per noun.

    For each noun with a matched_type, calls the LLM with a scoped
    extraction prompt. Nouns without a matched_type are carried through
    as unmatched (no extraction).

    Args:
        section_number: MasterFormat section number.
        section_title: Section title if known.
        part2_text: Part 2 text.
        nouns: List of NounIdentification from Pass 1.
        vocabulary: Output of assemble_vocabulary().
        llm_caller: Callable for LLM invocation.

    Returns:
        List of NounExtraction with per-noun results.
    """
    valid_props = build_valid_properties(vocabulary)
    noun_extractions: list[NounExtraction] = []

    for noun in nouns:
        ne = NounExtraction(
            noun_phrase=noun.noun_phrase,
            matched_type=noun.matched_type,
            qualifiers=noun.qualifiers,
            context=noun.context,
        )

        if noun.matched_type is None:
            # Unmatched type — no extraction possible
            ne.attribution_status = "unmatched_type"
            noun_extractions.append(ne)
            continue

        # Build and send per-noun prompt
        prompt = build_per_noun_extraction_prompt(
            section_number=section_number,
            section_title=section_title,
            part2_text=part2_text,
            noun_phrase=noun.noun_phrase,
            matched_type=noun.matched_type,
            vocabulary=vocabulary,
        )

        try:
            response_text = await llm_caller(prompt)
        except Exception as e:
            logger.error(
                f"LLM per-noun extraction failed for "
                f"'{noun.noun_phrase}' in {section_number}: {e}"
            )
            noun_extractions.append(ne)
            continue

        extractions, unrec, xrefs = parse_per_noun_extraction_response(
            response_text,
            noun.matched_type,
            valid_props,
        )

        ne.extractions = extractions
        ne.unrecognized = unrec
        ne.cross_references = xrefs
        noun_extractions.append(ne)

    return noun_extractions


async def extract_section_multi_pass(
    db: AsyncSession,
    section_number: str,
    section_title: str | None,
    part2_text: str,
    part1_text: str | None,
    section_division: str,
    llm_caller: LLMCaller,
    vocabulary: dict[str, dict[str, list[PropertyDef]]] | None = None,
) -> SectionExtraction:
    """
    Multi-pass extraction for a single spec section (v2).

    Orchestrates: Pass 1 (noun identification) → Pass 2 (per-noun extraction)
    → Deterministic attribution.

    Also populates backward-compatible flat lists by aggregating across nouns.

    Args:
        db: Async database session (for attribution queries).
        section_number: MasterFormat section number.
        section_title: Section title if known.
        part2_text: Part 2 text from WP-16.
        part1_text: Part 1 text (for Related Sections parsing). May be None.
        section_division: Two-digit division code.
        llm_caller: Callable for LLM invocation.

    Returns:
        SectionExtraction with noun-organized and flat-aggregated results.
    """
    if not part2_text or not part2_text.strip():
        return SectionExtraction(
            section_number=section_number,
            status="failed",
            error="No Part 2 text available for extraction",
        )

    # Assemble vocabulary (use provided vocabulary if given, e.g., from firm types)
    if vocabulary is None:
        related_divs = parse_related_sections(part1_text)
        vocabulary = assemble_vocabulary(section_division, related_divs)

    has_vocab = bool(vocabulary.get("primary")) or bool(vocabulary.get("secondary"))
    if not has_vocab:
        return SectionExtraction(
            section_number=section_number,
            status="failed",
            error=f"No element types configured for Division {section_division}",
        )

    # ── Pass 1: Noun Identification ──
    section_nouns = await identify_nouns(
        section_number=section_number,
        section_title=section_title,
        part2_text=part2_text,
        vocabulary=vocabulary,
        llm_caller=llm_caller,
    )

    if not section_nouns.nouns:
        return SectionExtraction(
            section_number=section_number,
            status="extracted",
            pass1_response={"nouns": []},
            nouns=[],
        )

    # ── Pass 2: Per-Noun Extraction ──
    noun_extractions = await extract_per_noun(
        section_number=section_number,
        section_title=section_title,
        part2_text=part2_text,
        nouns=section_nouns.nouns,
        vocabulary=vocabulary,
        llm_caller=llm_caller,
    )

    # ── Deterministic Attribution ──
    noun_extractions = await attribute_nouns_to_elements(db, noun_extractions)

    # ── Aggregate flat lists for backward compatibility ──
    all_extractions: list[ExtractionItem] = []
    all_unrecognized: list[UnrecognizedItem] = []
    all_cross_refs: list[CrossReferenceItem] = []

    for ne in noun_extractions:
        all_extractions.extend(ne.extractions)
        all_unrecognized.extend(ne.unrecognized)
        all_cross_refs.extend(ne.cross_references)

    # Deduplicate cross-references by section_number
    seen_xrefs: set[str] = set()
    deduped_xrefs: list[CrossReferenceItem] = []
    for xr in all_cross_refs:
        if xr.section_number not in seen_xrefs:
            seen_xrefs.add(xr.section_number)
            deduped_xrefs.append(xr)

    # Store Pass 1 raw output for audit trail (D-26)
    pass1_data = {
        "nouns": [n.model_dump() for n in section_nouns.nouns],
    }

    return SectionExtraction(
        section_number=section_number,
        status="extracted",
        pass1_response=pass1_data,
        nouns=noun_extractions,
        extractions=all_extractions,
        unrecognized=all_unrecognized,
        cross_references=deduped_xrefs,
    )


# ─── Batch Orchestration ─────────────────────────────────────────


async def _load_preprocess_sections(
    db: AsyncSession,
    specification_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """
    Load confirmed sections from WP-16 via specification → spec_section connections.

    Returns list of dicts with section metadata and Part 1/2/3 text.
    """
    # Get connections from specification to spec_sections
    result = await db.execute(
        select(Connection, Item)
        .join(
            Item,
            Item.id == Connection.target_item_id,
        )
        .where(
            and_(
                Connection.source_item_id == specification_id,
                Item.item_type == "spec_section",
            )
        )
    )
    rows = result.all()

    sections = []
    for conn, section_item in rows:
        conn_props = conn.properties or {}
        section_props = section_item.properties or {}

        # Extract division from section identifier (first 2 digits)
        identifier = section_item.identifier or ""
        division = identifier.replace(" ", "")[:2] if identifier else ""

        sections.append(
            {
                "section_number": conn_props.get("section_number", identifier),
                "section_title": conn_props.get("detected_title")
                or section_props.get("title"),
                "part1_text": conn_props.get("part1_text"),
                "part2_text": conn_props.get("part2_text"),
                "part3_text": conn_props.get("part3_text"),
                "division": division,
                "spec_section_item_id": section_item.id,
                "match_confidence": conn_props.get("match_confidence", 0.0),
            }
        )

    return sections


async def run_extraction(
    db: AsyncSession,
    specification_id: uuid.UUID,
    preprocess_batch_id: uuid.UUID,
    context_id: uuid.UUID,
    section_numbers: list[str] | None = None,
    llm_caller: LLMCaller | None = None,
    vocabulary: dict[str, dict[str, list[PropertyDef]]] | None = None,
) -> tuple[Item, dict[str, SectionExtraction]]:
    """
    Run multi-pass extraction for all (or specified) sections of a preprocessed spec.

    Creates an extraction_batch item, runs multi-pass LLM extraction per section,
    and stores results on the batch.

    Args:
        db: Async database session.
        specification_id: UUID of the specification item.
        preprocess_batch_id: UUID of the confirmed WP-16 preprocess batch.
        context_id: UUID of the milestone / issuance context.
        section_numbers: Optional list of specific sections to extract.
                        If None, extracts all confirmed sections.
        llm_caller: Optional LLM caller override (for testing).

    Returns:
        Tuple of (extraction_batch_item, dict of section_number → SectionExtraction).

    Raises:
        ValueError: If preprocess batch not found or not confirmed.
    """
    caller = llm_caller or _default_extraction_caller

    # Validate preprocess batch
    batch_result = await db.execute(
        select(Item).where(
            and_(
                Item.id == preprocess_batch_id,
                Item.item_type == "preprocess_batch",
            )
        )
    )
    preprocess_batch = batch_result.scalar_one_or_none()
    if not preprocess_batch:
        raise ValueError(f"Preprocess batch {preprocess_batch_id} not found")

    batch_props = preprocess_batch.properties or {}
    if batch_props.get("status") != "confirmed":
        raise ValueError(
            f"Preprocess batch {preprocess_batch_id} is not confirmed "
            f"(status: {batch_props.get('status')})"
        )

    # Validate specification exists
    spec_result = await db.execute(select(Item).where(Item.id == specification_id))
    spec_item = spec_result.scalar_one_or_none()
    if not spec_item:
        raise ValueError(f"Specification {specification_id} not found")

    # Validate context exists
    ctx_result = await db.execute(select(Item).where(Item.id == context_id))
    ctx_item = ctx_result.scalar_one_or_none()
    if not ctx_item:
        raise ValueError(f"Context milestone {context_id} not found")

    # Load sections
    all_sections = await _load_preprocess_sections(db, specification_id)

    # Filter to requested sections
    if section_numbers:
        requested = set(section_numbers)
        sections = [s for s in all_sections if s["section_number"] in requested]
    else:
        sections = all_sections

    # Create extraction_batch item
    extraction_batch = Item(
        item_type="extraction_batch",
        identifier=f"Extraction-{spec_item.identifier or spec_item.id}",
        properties={
            "status": "extracting",
            "specification_item_id": str(specification_id),
            "preprocess_batch_id": str(preprocess_batch_id),
            "context_id": str(context_id),
            "sections_total": len(sections),
            "sections_extracted": 0,
            "sections_failed": 0,
        },
    )
    db.add(extraction_batch)
    await db.flush()
    await db.refresh(extraction_batch)

    # Create connections: extraction_batch → preprocess_batch, spec, milestone
    for target_id in [preprocess_batch_id, specification_id, context_id]:
        db.add(
            Connection(
                source_item_id=extraction_batch.id,
                target_item_id=target_id,
                properties={"relationship": "extraction_provenance"},
            )
        )

    # If no vocabulary provided, build from firm types in DB
    if vocabulary is None:
        from app.services.dynamic_types import get_firm_types

        # Find any firm (for batch extraction, use the firm's type vocabulary)
        firm_result = await db.execute(
            select(Item).where(Item.item_type == "firm").limit(1)
        )
        firm_item = firm_result.scalar_one_or_none()
        if firm_item:
            firm_types = await get_firm_types(db, firm_item.id)
            # Build vocabulary from firm types with masterformat_divisions
            all_divisions_vocab: dict[str, dict[str, list[PropertyDef]]] = {}
            for type_name, tc in firm_types.items():
                for div in tc.masterformat_divisions:
                    if div not in all_divisions_vocab:
                        all_divisions_vocab[div] = {}
                    all_divisions_vocab[div][type_name] = list(tc.properties)
            # vocabulary will be resolved per-section below using this lookup
            _firm_vocab_by_division = all_divisions_vocab
        else:
            _firm_vocab_by_division = {}
    else:
        _firm_vocab_by_division = None  # sentinel: use the provided vocabulary

    # Run multi-pass extraction per section
    results: dict[str, SectionExtraction] = {}
    sections_extracted = 0
    sections_failed = 0

    for section_data in sections:
        section_num = section_data["section_number"]
        division = section_data["division"]

        if not division:
            logger.warning(f"Section {section_num} has no division, skipping")
            results[section_num] = SectionExtraction(
                section_number=section_num,
                status="failed",
                error="No MasterFormat division could be determined",
            )
            sections_failed += 1
            continue

        # Resolve vocabulary for this section's division
        if vocabulary is not None:
            section_vocab = vocabulary
        elif _firm_vocab_by_division is not None:
            primary = _firm_vocab_by_division.get(division, {})
            section_vocab = {"primary": primary, "secondary": {}} if primary else None
        else:
            section_vocab = None

        extraction = await extract_section_multi_pass(
            db=db,
            section_number=section_num,
            section_title=section_data["section_title"],
            part2_text=section_data["part2_text"] or "",
            part1_text=section_data["part1_text"],
            section_division=division,
            llm_caller=caller,
            vocabulary=section_vocab,
        )

        results[section_num] = extraction

        if extraction.status == "failed":
            sections_failed += 1
        else:
            sections_extracted += 1

    # Update batch with results
    batch_props = dict(extraction_batch.properties)
    batch_props["status"] = "extracted"
    batch_props["sections_extracted"] = sections_extracted
    batch_props["sections_failed"] = sections_failed
    batch_props["extraction_results"] = {
        "sections": {num: ext.model_dump() for num, ext in results.items()}
    }
    extraction_batch.properties = batch_props

    await db.flush()

    return extraction_batch, results
