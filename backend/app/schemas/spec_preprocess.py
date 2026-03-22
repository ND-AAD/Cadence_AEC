"""
Schemas for WP-16: Specification Preprocessing – PDF to Sections.

Defines request/response models for the spec preprocessing pipeline:
  - PDF upload → section identification → user confirmation
  - Structured output bridging WP-16 (preprocessing) to WP-17 (LLM extraction)
"""

import uuid
from typing import Optional

from pydantic import BaseModel, Field


# ─── Internal / Intermediate Models ──────────────────────────────


class PageContent(BaseModel):
    """Text extracted from a single PDF page."""
    page_number: int
    text: str

    model_config = {"from_attributes": True}


class RawSectionMatch(BaseModel):
    """A detected MasterFormat section number before database matching."""
    section_number: str       # Normalized to "XX XX XX" format
    raw_match: str            # The original text that matched
    pattern_name: str         # Which regex pattern matched
    char_offset: int          # Character offset in full text
    page_number: int          # Page where match was found
    context_line: str         # Full line containing the match

    model_config = {"from_attributes": True}


class PartBoundaries(BaseModel):
    """Character offsets for Part 1/2/3 within a section's text."""
    part1_start: int | None = None
    part1_end: int | None = None
    part2_start: int | None = None
    part2_end: int | None = None
    part3_start: int | None = None
    part3_end: int | None = None

    model_config = {"from_attributes": True}


# ─── Response Models ─────────────────────────────────────────────


class IdentifiedSection(BaseModel):
    """A specification section identified and matched against MasterFormat."""
    section_number: str                          # "08 14 00"
    detected_title: str | None = None            # Title parsed from PDF
    page_start: int                              # First page of this section
    page_end: int                                # Last page of this section

    # Part boundaries (character offsets within section text)
    part1_text: str | None = None
    part2_text: str | None = None
    part3_text: str | None = None

    # MasterFormat database match
    masterformat_item_id: uuid.UUID | None = None   # Matched spec_section item
    masterformat_identifier: str | None = None       # e.g., "08 14 00"
    masterformat_title: str | None = None            # e.g., "Wood Doors"
    match_confidence: float = 0.0                    # 0.0–1.0

    model_config = {"from_attributes": True}


class UnmatchedSection(BaseModel):
    """A section number detected in PDF but not matched to any MasterFormat item."""
    section_number: str
    detected_title: str | None = None
    page_number: int
    context_line: str

    model_config = {"from_attributes": True}


class IdentifiedDocument(BaseModel):
    """Complete preprocessing result for a specification PDF."""
    total_pages: int
    identified_sections: list[IdentifiedSection] = Field(default_factory=list)
    unmatched_sections: list[UnmatchedSection] = Field(default_factory=list)
    preprocessing_notes: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SpecPreprocessResponse(BaseModel):
    """Response from POST /api/v1/spec/preprocess."""
    batch_id: uuid.UUID
    document: IdentifiedDocument
    message: str = "PDF preprocessed successfully"

    model_config = {"from_attributes": True}


# ─── Confirmation Models ─────────────────────────────────────────


class SectionConfirmation(BaseModel):
    """User confirmation/override for a single identified section."""
    section_number: str
    include: bool = True                                    # False to exclude
    masterformat_item_id: uuid.UUID | None = None           # Override detected match
    title_override: str | None = None                       # Override detected title

    model_config = {"from_attributes": True}


class ConfirmSectionsRequest(BaseModel):
    """Request body for POST /api/v1/spec/preprocess/{batch_id}/confirm-sections."""
    specification_item_id: uuid.UUID | None = None    # Use existing spec, or create new
    spec_name: str | None = None                       # Name for new specification item
    section_confirmations: list[SectionConfirmation] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ConfirmSectionsResponse(BaseModel):
    """Response from confirm-sections endpoint."""
    batch_id: uuid.UUID
    specification_item_id: uuid.UUID
    sections_confirmed: int
    connections_created: int
    message: str = "Sections confirmed successfully"

    model_config = {"from_attributes": True}


# ─── Batch Status Model ──────────────────────────────────────────


class PreprocessBatchStatus(BaseModel):
    """Response from GET /api/v1/spec/preprocess/{batch_id}."""
    batch_id: uuid.UUID
    status: str
    original_filename: str | None = None
    page_count: int | None = None
    sections_identified: int | None = None
    sections_matched: int | None = None
    document: IdentifiedDocument | None = None

    model_config = {"from_attributes": True}
