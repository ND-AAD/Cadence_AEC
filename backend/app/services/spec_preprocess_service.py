"""
Specification Preprocessing Service — WP-16.

Converts specification PDFs into structured, section-identified text
ready for downstream LLM extraction (WP-17).

Pipeline:
  1. PDF → per-page text extraction (pdfplumber)
  2. Full text → MasterFormat section boundary detection (regex)
  3. Section text → Part 1/2/3 boundary detection
  4. Detected sections → MasterFormat database matching
  5. Structured IdentifiedDocument output

All pure-function steps are synchronous and independently testable.
Only MasterFormat matching requires a database session.
"""

import io
import json
import logging
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import NamedTuple

import pdfplumber
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Connection, Item
from app.schemas.spec_preprocess import (
    IdentifiedDocument,
    IdentifiedSection,
    PageContent,
    PartBoundaries,
    RawSectionMatch,
    UnmatchedSection,
)

logger = logging.getLogger(__name__)


# ─── Constants ────────────────────────────────────────────────────

# Minimum repeated-line occurrence across pages to classify as header/footer
HEADER_FOOTER_THRESHOLD = 3

# Section detection regex patterns (priority order)
SECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    # "SECTION 08 14 00" — standard CSI header
    ("csi_keyword", re.compile(
        r"(?i)\bSECTION\s+(\d{2})\s+(\d{2})\s+(\d{2})\b"
    )),
    # "08 14 00 -" or "08 14 00 —" — number with separator at line start
    ("number_dash", re.compile(
        r"(?m)^\s*(\d{2})\s+(\d{2})\s+(\d{2})\s*[-—–]"
    )),
    # "08 14 00" — standalone at line start (no separator required)
    ("standalone", re.compile(
        r"(?m)^\s*(\d{2})\s+(\d{2})\s+(\d{2})\s"
    )),
    # "SECTION 081400" — compressed with keyword
    ("compressed_keyword", re.compile(
        r"(?i)\bSECTION\s+(\d{2})(\d{2})(\d{2})\b"
    )),
    # "081400" — compressed standalone at line start
    ("compressed_standalone", re.compile(
        r"(?m)^\s*(\d{2})(\d{2})(\d{2})\s"
    )),
]

# Part boundary patterns
PART_PATTERNS: list[tuple[int, re.Pattern]] = [
    # Part 1
    (1, re.compile(r"(?im)^\s*PART\s+(?:1|ONE)\b")),
    (1, re.compile(r"(?im)^\s*1\.\s*GENERAL\b")),
    # Part 2
    (2, re.compile(r"(?im)^\s*PART\s+(?:2|TWO)\b")),
    (2, re.compile(r"(?im)^\s*2\.\s*PRODUCTS?\b")),
    # Part 3
    (3, re.compile(r"(?im)^\s*PART\s+(?:3|THREE)\b")),
    (3, re.compile(r"(?im)^\s*3\.\s*EXECUTION\b")),
]

# End-of-section marker
END_OF_SECTION_PATTERN = re.compile(
    r"(?im)^\s*END\s+OF\s+SECTION\b"
)


# ─── 1. PDF Text Extraction ──────────────────────────────────────


def extract_pdf_text(pdf_bytes: bytes) -> tuple[list[PageContent], str]:
    """
    Extract text from a PDF, returning per-page content and full text.

    Handles:
      - Per-page text extraction with pdfplumber
      - Header/footer stripping (lines repeated across many pages)
      - Page-break normalization

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        Tuple of (list of PageContent, full concatenated text).

    Raises:
        ValueError: If PDF cannot be parsed.
    """
    pages: list[PageContent] = []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages.append(PageContent(
                    page_number=i + 1,
                    text=text,
                ))
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {e}") from e

    if not pages:
        raise ValueError("PDF contains no pages")

    # Strip headers/footers: lines appearing on many pages
    pages = _strip_headers_footers(pages)

    # Concatenate with page markers
    full_text = "\n".join(p.text for p in pages)

    return pages, full_text


def _strip_headers_footers(pages: list[PageContent]) -> list[PageContent]:
    """
    Remove lines that appear identically on many pages (likely headers/footers).

    Heuristic: if a line appears on >= HEADER_FOOTER_THRESHOLD pages,
    it's probably a header or footer.
    """
    if len(pages) < HEADER_FOOTER_THRESHOLD:
        return pages

    # Count line occurrences across pages
    line_counts: Counter[str] = Counter()
    for page in pages:
        # Use set to count each line at most once per page
        unique_lines = set(page.text.splitlines())
        for line in unique_lines:
            stripped = line.strip()
            if stripped:  # Skip blank lines
                line_counts[stripped] += 1

    # Identify repeated lines
    repeated_lines = {
        line for line, count in line_counts.items()
        if count >= HEADER_FOOTER_THRESHOLD
    }

    if not repeated_lines:
        return pages

    # Filter out repeated lines from each page
    cleaned: list[PageContent] = []
    for page in pages:
        filtered_lines = [
            line for line in page.text.splitlines()
            if line.strip() not in repeated_lines
        ]
        cleaned.append(PageContent(
            page_number=page.page_number,
            text="\n".join(filtered_lines),
        ))

    return cleaned


# ─── 2. MasterFormat Section Detection ───────────────────────────


def normalize_section_number(raw: str) -> str:
    """
    Normalize a MasterFormat section number to 'XX XX XX' format.

    Examples:
        '081400'     → '08 14 00'
        '08 14 00'   → '08 14 00'
        '08  14  00' → '08 14 00'
    """
    # Strip non-digits
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 6:
        return raw.strip()
    return f"{digits[0:2]} {digits[2:4]} {digits[4:6]}"


def detect_section_boundaries(full_text: str) -> list[RawSectionMatch]:
    """
    Scan full PDF text for MasterFormat section number patterns.

    Returns a list of detected section starts, sorted by character offset.
    Filters false positives like TOC entries (dot leaders) and
    section numbers embedded in reference lists.

    Args:
        full_text: The complete extracted text from the PDF.

    Returns:
        Sorted list of RawSectionMatch objects.
    """
    matches: list[RawSectionMatch] = []
    seen_offsets: set[int] = set()  # Deduplicate overlapping patterns

    for pattern_name, pattern in SECTION_PATTERNS:
        for m in pattern.finditer(full_text):
            # Build normalized section number from capture groups
            groups = m.groups()
            raw_number = " ".join(groups)
            normalized = normalize_section_number(raw_number)

            # Deduplicate: skip if we already matched at this offset
            offset = m.start()
            if any(abs(offset - seen) < 10 for seen in seen_offsets):
                continue

            # Get the full line for context
            line_start = full_text.rfind("\n", 0, offset) + 1
            line_end = full_text.find("\n", offset)
            if line_end == -1:
                line_end = len(full_text)
            context_line = full_text[line_start:line_end].strip()

            # Filter false positives
            if _is_false_positive(context_line, normalized, full_text, offset):
                continue

            # Determine page number (approximate from text position)
            page_number = _estimate_page_number(full_text, offset)

            matches.append(RawSectionMatch(
                section_number=normalized,
                raw_match=m.group(0),
                pattern_name=pattern_name,
                char_offset=offset,
                page_number=page_number,
                context_line=context_line,
            ))
            seen_offsets.add(offset)

    # Sort by position in text
    matches.sort(key=lambda m: m.char_offset)

    return matches


def _is_false_positive(
    context_line: str,
    section_number: str,
    full_text: str,
    offset: int,
) -> bool:
    """
    Check if a detected section number is a false positive.

    False positives:
      - TOC entries (lines with dot leaders: "08 14 00 ........... 15")
      - Reference lists ("refer to Section 08 14 00")
      - Page number patterns
    """
    # TOC: dot leaders
    if "...." in context_line or "…" in context_line:
        return True

    # Reference mentions: "refer to", "see Section", "per Section"
    lower_line = context_line.lower()
    ref_patterns = ["refer to", "see section", "per section", "in accordance with"]
    for ref in ref_patterns:
        if ref in lower_line:
            # Only false positive if the section number comes AFTER the reference phrase
            ref_idx = lower_line.find(ref)
            num_idx = lower_line.find(section_number.replace(" ", "").lower())
            if num_idx < 0:
                num_idx = lower_line.find(section_number.lower())
            if num_idx >= 0 and ref_idx < num_idx:
                return True

    return False


def _estimate_page_number(full_text: str, char_offset: int) -> int:
    """Estimate page number from character offset using newline density."""
    # Simple heuristic: count double-newlines as rough page breaks
    # This is approximate — actual page tracking happens in extract_pdf_text
    text_before = full_text[:char_offset]
    # Assume ~3000 chars per page for typical specs
    return max(1, len(text_before) // 3000 + 1)


# ─── 3. Part 1/2/3 Boundary Detection ────────────────────────────


def find_part_boundaries(section_text: str) -> PartBoundaries:
    """
    Within a section's text, locate Part 1, Part 2, and Part 3 boundaries.

    Looks for patterns like:
      - "PART 1 - GENERAL"
      - "PART TWO - PRODUCTS"
      - "2. PRODUCTS"
      - etc.

    Args:
        section_text: The full text of a single specification section.

    Returns:
        PartBoundaries with start/end offsets for each part.
        None values indicate the part was not detected.
    """
    # Find first match for each part number
    part_positions: dict[int, int] = {}

    for part_num, pattern in PART_PATTERNS:
        if part_num in part_positions:
            continue  # Already found this part
        m = pattern.search(section_text)
        if m:
            part_positions[part_num] = m.start()

    # Build boundaries based on what was found
    boundaries = PartBoundaries()

    # Get sorted parts we found
    found_parts = sorted(part_positions.items())

    for i, (part_num, start) in enumerate(found_parts):
        # End is start of next part, or end of section
        if i + 1 < len(found_parts):
            end = found_parts[i + 1][1]
        else:
            # Check for END OF SECTION marker
            eos_match = END_OF_SECTION_PATTERN.search(section_text, start)
            end = eos_match.start() if eos_match else len(section_text)

        if part_num == 1:
            boundaries.part1_start = start
            boundaries.part1_end = end
        elif part_num == 2:
            boundaries.part2_start = start
            boundaries.part2_end = end
        elif part_num == 3:
            boundaries.part3_start = start
            boundaries.part3_end = end

    return boundaries


def extract_part_text(
    section_text: str,
    boundaries: PartBoundaries,
) -> tuple[str | None, str | None, str | None]:
    """
    Extract Part 1, Part 2, and Part 3 text from section using boundaries.

    Returns:
        Tuple of (part1_text, part2_text, part3_text).
        None if that part was not detected.
    """
    part1 = None
    part2 = None
    part3 = None

    if boundaries.part1_start is not None and boundaries.part1_end is not None:
        part1 = section_text[boundaries.part1_start:boundaries.part1_end].strip()
    if boundaries.part2_start is not None and boundaries.part2_end is not None:
        part2 = section_text[boundaries.part2_start:boundaries.part2_end].strip()
    if boundaries.part3_start is not None and boundaries.part3_end is not None:
        part3 = section_text[boundaries.part3_start:boundaries.part3_end].strip()

    return part1, part2, part3


# ─── 4. MasterFormat Database Matching ────────────────────────────


async def load_spec_sections(
    db: AsyncSession,
    hint_division: str | None = None,
) -> dict[str, Item]:
    """
    Load all spec_section items from the database, keyed by identifier.

    Args:
        db: Async database session.
        hint_division: If provided, only load sections from this division.

    Returns:
        Dict mapping normalized identifier → Item.
    """
    query = select(Item).where(Item.item_type == "spec_section")

    result = await db.execute(query)
    items = result.scalars().all()

    section_map: dict[str, Item] = {}
    for item in items:
        normalized_id = normalize_section_number(item.identifier or "")
        # Apply hint_division filter (Python-side for SQLite compatibility)
        if hint_division:
            item_division = None
            if isinstance(item.properties, dict):
                item_division = item.properties.get("division")
            if item_division != hint_division:
                continue
        section_map[normalized_id] = item

    return section_map


async def match_sections_to_masterformat(
    db: AsyncSession,
    raw_matches: list[RawSectionMatch],
    full_text: str,
    hint_division: str | None = None,
) -> tuple[list[IdentifiedSection], list[UnmatchedSection]]:
    """
    Match detected section numbers against seeded MasterFormat items.

    Strategy:
      1. Exact match on normalized identifier
      2. Group-level match (XX XX 00) if exact not found
      3. Unmatched sections returned separately

    Args:
        db: Async database session.
        raw_matches: Detected section boundaries from the PDF.
        full_text: Full extracted text for slicing section content.
        hint_division: Optional division hint to narrow matching.

    Returns:
        Tuple of (identified_sections, unmatched_sections).
    """
    spec_sections = await load_spec_sections(db, hint_division)

    identified: list[IdentifiedSection] = []
    unmatched: list[UnmatchedSection] = []

    for i, raw in enumerate(raw_matches):
        # Determine section text boundaries
        section_start = raw.char_offset
        if i + 1 < len(raw_matches):
            section_end = raw_matches[i + 1].char_offset
        else:
            section_end = len(full_text)

        section_text = full_text[section_start:section_end]

        # Detect title from context line
        detected_title = _extract_title_from_context(raw.context_line, raw.section_number)

        # Page range
        page_start = raw.page_number
        page_end = raw_matches[i + 1].page_number if i + 1 < len(raw_matches) else page_start

        # Find Part 1/2/3
        boundaries = find_part_boundaries(section_text)
        part1, part2, part3 = extract_part_text(section_text, boundaries)

        # Match against database
        normalized = raw.section_number
        matched_item: Item | None = None
        confidence = 0.0

        # Try exact match
        if normalized in spec_sections:
            matched_item = spec_sections[normalized]
            confidence = 1.0
        else:
            # Try group-level match (XX XX 00)
            digits = re.sub(r"\D", "", normalized)
            if len(digits) == 6:
                group_id = f"{digits[0:2]} {digits[2:4]} 00"
                if group_id in spec_sections:
                    matched_item = spec_sections[group_id]
                    confidence = 0.8

        if matched_item:
            mf_title = None
            if isinstance(matched_item.properties, dict):
                mf_title = matched_item.properties.get("title")

            identified.append(IdentifiedSection(
                section_number=normalized,
                detected_title=detected_title,
                page_start=page_start,
                page_end=page_end,
                part1_text=part1,
                part2_text=part2,
                part3_text=part3,
                masterformat_item_id=matched_item.id,
                masterformat_identifier=matched_item.identifier,
                masterformat_title=mf_title,
                match_confidence=confidence,
            ))
        else:
            unmatched.append(UnmatchedSection(
                section_number=normalized,
                detected_title=detected_title,
                page_number=raw.page_number,
                context_line=raw.context_line,
            ))

    return identified, unmatched


def _extract_title_from_context(context_line: str, section_number: str) -> str | None:
    """
    Extract a section title from the context line.

    Patterns:
      "SECTION 08 14 00 - WOOD DOORS" → "WOOD DOORS"
      "08 14 00 — Wood Doors"         → "Wood Doors"
      "081400 WOOD DOORS"              → "WOOD DOORS"
    """
    # Remove common prefixes
    line = context_line.strip()

    # Remove "SECTION" prefix
    line = re.sub(r"(?i)^SECTION\s+", "", line)

    # Remove the section number (spaced or compressed)
    digits = re.sub(r"\D", "", section_number)
    # Remove spaced version
    line = line.replace(section_number, "", 1).strip()
    # Remove compressed version
    if digits in line:
        line = line.replace(digits, "", 1).strip()

    # Remove leading separators
    line = re.sub(r"^[-—–:.\s]+", "", line).strip()

    return line if line else None


# ─── 5. Orchestrator ─────────────────────────────────────────────


async def preprocess_specification_pdf(
    db: AsyncSession,
    pdf_bytes: bytes,
    filename: str,
    hint_division: str | None = None,
) -> tuple[Item, IdentifiedDocument]:
    """
    Full preprocessing pipeline: extract → detect → match → structure.

    Creates a preprocess_batch item to track the operation.

    Args:
        db: Async database session.
        pdf_bytes: Raw PDF file bytes.
        filename: Original filename.
        hint_division: Optional division to narrow MasterFormat matching.

    Returns:
        Tuple of (batch_item, identified_document).

    Raises:
        ValueError: If PDF is invalid or empty.
    """
    preprocessing_notes: list[str] = []

    # Step 1: Extract text
    try:
        pages, full_text = extract_pdf_text(pdf_bytes)
    except ValueError as e:
        # Create failed batch
        batch = Item(
            item_type="preprocess_batch",
            identifier=f"Preprocess-{filename}",
            properties={
                "original_filename": filename,
                "status": "failed",
                "page_count": 0,
                "sections_identified": 0,
                "sections_matched": 0,
            },
        )
        db.add(batch)
        await db.flush()
        await db.refresh(batch)

        return batch, IdentifiedDocument(
            total_pages=0,
            preprocessing_notes=[f"PDF parsing failed: {e}"],
        )

    total_pages = len(pages)

    # Step 2: Detect section boundaries
    raw_matches = detect_section_boundaries(full_text)

    if not raw_matches:
        preprocessing_notes.append(
            "No MasterFormat section numbers detected in PDF. "
            "Check that the document contains specification sections."
        )

    # Step 3: Match against MasterFormat database + extract Parts
    identified, unmatched = await match_sections_to_masterformat(
        db, raw_matches, full_text, hint_division
    )

    if unmatched:
        preprocessing_notes.append(
            f"{len(unmatched)} section(s) detected but not matched to "
            f"seeded MasterFormat items: "
            f"{', '.join(u.section_number for u in unmatched)}"
        )

    # Check for sections without Part 2 content
    no_part2 = [s for s in identified if not s.part2_text]
    if no_part2:
        preprocessing_notes.append(
            f"{len(no_part2)} section(s) have no Part 2 (Products) content detected: "
            f"{', '.join(s.section_number for s in no_part2)}"
        )

    # Build document
    document = IdentifiedDocument(
        total_pages=total_pages,
        identified_sections=identified,
        unmatched_sections=unmatched,
        preprocessing_notes=preprocessing_notes,
    )

    # Create batch item
    batch = Item(
        item_type="preprocess_batch",
        identifier=f"Preprocess-{filename}",
        properties={
            "original_filename": filename,
            "status": "identified",
            "page_count": total_pages,
            "sections_identified": len(identified) + len(unmatched),
            "sections_matched": len(identified),
            # Store document for retrieval (serialized)
            "document_json": document.model_dump_json(),
        },
    )
    db.add(batch)
    await db.flush()
    await db.refresh(batch)

    return batch, document


# ─── 6. Confirmation Handler ─────────────────────────────────────


async def confirm_sections(
    db: AsyncSession,
    batch_id: uuid.UUID,
    specification_item_id: uuid.UUID | None,
    spec_name: str | None,
    confirmations: list,  # list[SectionConfirmation]
) -> tuple[Item, int, int]:
    """
    Process user confirmation of identified sections.

    Creates or reuses a specification item, then creates connections
    from specification → confirmed spec_section items, storing Part 2
    text in connection properties for WP-17 retrieval.

    Args:
        db: Async database session.
        batch_id: UUID of the preprocess_batch item.
        specification_item_id: Optional existing specification item UUID.
        spec_name: Name for new specification item (if creating).
        confirmations: List of SectionConfirmation from user.

    Returns:
        Tuple of (specification_item, sections_confirmed, connections_created).

    Raises:
        ValueError: If batch not found or already confirmed.
    """
    # Load batch item
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
        raise ValueError(f"Preprocess batch {batch_id} not found")

    if isinstance(batch.properties, dict) and batch.properties.get("status") == "confirmed":
        raise ValueError(f"Batch {batch_id} already confirmed")

    # Load stored document from batch
    doc_json = None
    if isinstance(batch.properties, dict):
        doc_json = batch.properties.get("document_json")

    if not doc_json:
        raise ValueError("No preprocessing document found on batch")

    document = IdentifiedDocument.model_validate_json(doc_json)

    # Build lookup of identified sections
    section_lookup: dict[str, IdentifiedSection] = {
        s.section_number: s for s in document.identified_sections
    }

    # Get or create specification item
    if specification_item_id:
        spec_result = await db.execute(
            select(Item).where(Item.id == specification_item_id)
        )
        spec_item = spec_result.scalar_one_or_none()
        if not spec_item:
            raise ValueError(f"Specification item {specification_item_id} not found")
    else:
        spec_item = Item(
            item_type="specification",
            identifier=spec_name or f"Specification ({batch.properties.get('original_filename', 'unknown')})",
            properties={
                "name": spec_name or "Specification",
            },
        )
        db.add(spec_item)
        await db.flush()
        await db.refresh(spec_item)

    # Process confirmations
    sections_confirmed = 0
    connections_created = 0

    # If no explicit confirmations, confirm all identified sections
    if not confirmations:
        sections_to_confirm = [
            (s.section_number, s.masterformat_item_id, None)
            for s in document.identified_sections
            if s.masterformat_item_id
        ]
    else:
        sections_to_confirm = []
        for conf in confirmations:
            if not conf.include:
                continue
            # Use override masterformat_item_id if provided, else from detection
            mf_id = conf.masterformat_item_id
            if not mf_id and conf.section_number in section_lookup:
                mf_id = section_lookup[conf.section_number].masterformat_item_id
            if mf_id:
                sections_to_confirm.append(
                    (conf.section_number, mf_id, conf.title_override)
                )

    for section_number, mf_item_id, title_override in sections_to_confirm:
        section_data = section_lookup.get(section_number)

        # Build connection properties — store Part 2 text for WP-17
        conn_props: dict = {
            "confirmed_by": "user",
            "section_number": section_number,
        }
        if section_data:
            if section_data.part2_text:
                conn_props["part2_text"] = section_data.part2_text
            if section_data.part1_text:
                conn_props["part1_text"] = section_data.part1_text
            if section_data.part3_text:
                conn_props["part3_text"] = section_data.part3_text
            conn_props["match_confidence"] = section_data.match_confidence
            conn_props["detected_title"] = title_override or section_data.detected_title

        # Check if connection already exists
        existing = await db.execute(
            select(Connection).where(
                and_(
                    Connection.source_item_id == spec_item.id,
                    Connection.target_item_id == mf_item_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            sections_confirmed += 1
            continue  # Already connected

        # Create connection: specification → spec_section
        conn = Connection(
            source_item_id=spec_item.id,
            target_item_id=mf_item_id,
            properties=conn_props,
        )
        db.add(conn)
        connections_created += 1
        sections_confirmed += 1

    # Update batch status
    if isinstance(batch.properties, dict):
        updated_props = dict(batch.properties)
        updated_props["status"] = "confirmed"
        updated_props["specification_item_id"] = str(spec_item.id)
        batch.properties = updated_props

    await db.flush()

    return spec_item, sections_confirmed, connections_created
