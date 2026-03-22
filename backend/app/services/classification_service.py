"""
MasterFormat classification service — WP-15.

Classifies imported construction elements into MasterFormat Divisions
using batch LLM calls.  Division-level only (coarse); WP-18 refines
to Section/Subsection when sub-section disagreements arise.

Architecture:
  - Cache via existing connections: if an element already connects to
    a spec_section, skip classification.
  - Batch processing: up to 50 elements per LLM prompt.
  - Graceful degradation: API failures return empty results, never
    block the import pipeline.
  - Confidence stored in Connection.properties for downstream review.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.core import Connection, Item

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


# ─── Data Types ──────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """Result of classifying a single element."""
    item_id: uuid.UUID
    item_identifier: str | None
    section_id: uuid.UUID
    section_identifier: str       # e.g., "08"
    section_title: str            # e.g., "Openings"
    confidence: str               # "high", "medium", "low"
    needs_review: bool = False


# ─── LLM Caller Type ────────────────────────────────────────

# Callable that takes a prompt and returns the LLM response text.
# Abstracted for testability — tests inject a mock, production uses Anthropic.
LLMCaller = Callable[[str], Awaitable[str]]


async def _default_llm_caller(prompt: str) -> str:
    """Call Anthropic API with the classification prompt."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=settings.CLASSIFICATION_MODEL,
        max_tokens=256,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ─── Core Classification ────────────────────────────────────

async def classify_elements(
    db: AsyncSession,
    items: list[Item],
    item_properties: dict[uuid.UUID, dict],
    llm_caller: LLMCaller | None = None,
) -> list[ClassificationResult]:
    """
    Classify imported elements into MasterFormat Divisions.

    Args:
        db: Active async database session.
        items: List of imported Item objects to classify.
        item_properties: Mapping of item_id → imported property dicts.
        llm_caller: Optional callable for LLM invocation (for testing).
                    Defaults to Anthropic API via _default_llm_caller.

    Returns:
        List of ClassificationResult for successfully classified items.
    """
    if not items:
        return []

    caller = llm_caller or _default_llm_caller

    # ── Step 1: Load MasterFormat divisions (level 0) ─────────
    divisions = await _load_divisions(db)
    if not divisions:
        logger.warning("No MasterFormat divisions found — skipping classification")
        return []

    # ── Step 2: Filter out already-classified items ───────────
    unclassified = await _filter_unclassified(db, items, divisions)
    if not unclassified:
        logger.info("All items already classified — skipping LLM call")
        return []

    # ── Step 3: Batch classify ────────────────────────────────
    all_results: list[ClassificationResult] = []

    for batch_start in range(0, len(unclassified), BATCH_SIZE):
        batch = unclassified[batch_start:batch_start + BATCH_SIZE]

        try:
            batch_results = await _classify_batch(
                db, batch, item_properties, divisions, caller,
            )
            all_results.extend(batch_results)
        except Exception as e:
            logger.error(f"Classification batch failed: {e}")
            # Graceful degradation — continue with next batch

    return all_results


# ─── Helpers ─────────────────────────────────────────────────

async def _load_divisions(
    db: AsyncSession,
) -> dict[str, Item]:
    """Load MasterFormat division items (level 0) keyed by identifier."""
    result = await db.execute(
        select(Item).where(
            and_(
                Item.item_type == "spec_section",
            )
        )
    )
    all_sections = list(result.scalars().all())

    # Filter to level 0 (divisions) Python-side for SQLite compat
    divisions = {}
    for section in all_sections:
        if section.properties.get("level") == 0:
            divisions[section.identifier] = section

    return divisions


async def _filter_unclassified(
    db: AsyncSession,
    items: list[Item],
    divisions: dict[str, Item],
) -> list[Item]:
    """Return only items not already connected to a spec_section."""
    if not items:
        return []

    item_ids = [i.id for i in items]
    division_ids = [d.id for d in divisions.values()]

    # Find items that already have connections to any spec_section
    result = await db.execute(
        select(Connection.source_item_id).where(
            and_(
                Connection.source_item_id.in_(item_ids),
                Connection.target_item_id.in_(division_ids),
            )
        )
    )
    already_classified = {row[0] for row in result.all()}

    return [i for i in items if i.id not in already_classified]


def _build_classification_prompt(
    items: list[Item],
    item_properties: dict[uuid.UUID, dict],
    divisions: dict[str, Item],
) -> str:
    """Build the batch classification prompt."""
    # Division reference
    division_lines = []
    for identifier, div_item in sorted(divisions.items()):
        title = div_item.properties.get("title", identifier)
        division_lines.append(f"{identifier} — {title}")

    # Element list
    element_lines = []
    for idx, item in enumerate(items, 1):
        props = item_properties.get(item.id, {})
        # Format properties as key: value pairs
        prop_strs = [f"{k}: {v}" for k, v in sorted(props.items()) if v]
        props_display = ", ".join(prop_strs) if prop_strs else "no properties"
        element_lines.append(
            f'{idx}. "{item.identifier}" ({item.item_type}) — {props_display}'
        )

    prompt = f"""Classify each construction element into the most appropriate MasterFormat Division.

Available Divisions:
{chr(10).join(division_lines)}

Elements to classify:
{chr(10).join(element_lines)}

Respond ONLY with a JSON array. Each entry must have:
- "element": the element number (integer)
- "division": the division identifier (string, e.g. "08")
- "confidence": "high", "medium", or "low"

Example response:
[{{"element": 1, "division": "08", "confidence": "high"}}]

JSON response:"""

    return prompt


def _parse_classification_response(
    response_text: str,
    items: list[Item],
    divisions: dict[str, Item],
) -> list[dict[str, Any]]:
    """Parse the LLM response JSON into classification mappings."""
    # Strip any markdown fencing
    text = response_text.strip()
    if text.startswith("```"):
        # Remove ```json and ``` markers
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM classification response: {text[:200]}")
        return []

    if not isinstance(parsed, list):
        logger.error(f"LLM classification response is not a list: {type(parsed)}")
        return []

    results = []
    for entry in parsed:
        try:
            element_idx = int(entry.get("element", 0))
            division_id = str(entry.get("division", "")).strip()
            confidence = str(entry.get("confidence", "medium")).strip().lower()

            if confidence not in ("high", "medium", "low"):
                confidence = "medium"

            if element_idx < 1 or element_idx > len(items):
                continue
            if division_id not in divisions:
                continue

            results.append({
                "item": items[element_idx - 1],
                "division": divisions[division_id],
                "confidence": confidence,
            })
        except (ValueError, TypeError, IndexError):
            continue

    return results


async def _classify_batch(
    db: AsyncSession,
    items: list[Item],
    item_properties: dict[uuid.UUID, dict],
    divisions: dict[str, Item],
    caller: LLMCaller,
) -> list[ClassificationResult]:
    """Classify a single batch of items via LLM call."""
    prompt = _build_classification_prompt(items, item_properties, divisions)

    # Call the LLM
    response_text = await caller(prompt)

    # Parse response
    mappings = _parse_classification_response(response_text, items, divisions)

    # Create connections and build results
    results: list[ClassificationResult] = []
    for mapping in mappings:
        item = mapping["item"]
        division = mapping["division"]
        confidence = mapping["confidence"]
        needs_review = confidence == "low"

        # Check for existing connection (safety — _filter_unclassified should have caught this)
        existing = await db.execute(
            select(Connection.id).where(
                and_(
                    Connection.source_item_id == item.id,
                    Connection.target_item_id == division.id,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Create connection: element → division
        conn = Connection(
            source_item_id=item.id,
            target_item_id=division.id,
            properties={
                "classification_confidence": confidence,
                "classified_by": "llm",
                "model": settings.CLASSIFICATION_MODEL,
                "needs_review": needs_review,
            },
        )
        db.add(conn)
        await db.flush()

        results.append(ClassificationResult(
            item_id=item.id,
            item_identifier=item.identifier,
            section_id=division.id,
            section_identifier=division.identifier,
            section_title=division.properties.get("title", ""),
            confidence=confidence,
            needs_review=needs_review,
        ))

    return results
