"""
Schemas for WP-17: Specification Extraction — LLM Pipeline.

Defines request/response models for the extraction pipeline:
  - Trigger extraction for preprocessed sections
  - Review extraction results (flat + conditional assertions, unrecognized terms)
  - User confirmation with corrections, rejections, and property promotion
  - Batch status tracking

Bridges WP-16 (preprocessing) output to WP-18 (propagation) input.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field


# ─── Extraction Output Models (LLM response structure) ─────────


class ConditionalAssertion(BaseModel):
    """A single value-condition pair within a conditional extraction."""

    value: str
    condition: str
    source_text: str

    model_config = {"from_attributes": True}


class ExtractionItem(BaseModel):
    """A single property extraction from a spec section."""

    property: str  # Property name (e.g., "material")
    element_type: str  # Type this applies to (e.g., "door")
    assertion_type: Literal["flat", "conditional"] = "flat"
    # Flat assertion fields
    value: str | None = None  # Extracted value (flat only)
    confidence: float = 0.0  # 0.0–1.0
    source_text: str = ""  # Exact clause cited
    # Conditional assertion fields
    assertions: list[ConditionalAssertion] | None = None  # For conditional only

    model_config = {"from_attributes": True}


class UnrecognizedItem(BaseModel):
    """A term found in the spec that doesn't match any known property."""

    term: str  # As found in text (e.g., "STC rating")
    value: str  # Extracted value
    context: str = ""  # Type context (e.g., "door acoustic requirements")
    source_text: str = ""  # Exact clause cited

    model_config = {"from_attributes": True}


class CrossReferenceItem(BaseModel):
    """A cross-reference to another spec section found in the text."""

    section_number: str  # Referenced section (e.g., "08 71 00")
    relationship: str  # What the reference is about (e.g., "hardware requirements")
    source_text: str = ""  # Exact clause containing the reference

    model_config = {"from_attributes": True}


# ─── Noun-Based Models (WP-17 v2: Multi-Pass Extraction) ──────


class NounIdentification(BaseModel):
    """A single noun identified in Pass 1 of multi-pass extraction."""

    noun_phrase: str  # Spec's own language (e.g., "hollow metal doors")
    matched_type: str | None = (
        None  # type_config type (e.g., "door"), or None if unmatched
    )
    qualifiers: dict[str, str] = Field(
        default_factory=dict
    )  # Narrowing attributes (e.g., {material: "hollow metal"})
    context: str = ""  # Brief description of what spec says about this item

    model_config = {"from_attributes": True}


class SectionNouns(BaseModel):
    """Pass 1 output for a section: all identified nouns."""

    section_number: str
    nouns: list[NounIdentification] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class NounExtraction(BaseModel):
    """Combined noun identification + Pass 2 extraction result."""

    noun_phrase: str
    matched_type: str | None = None
    qualifiers: dict[str, str] = Field(default_factory=dict)
    context: str = ""
    # Pass 2 results for this noun
    extractions: list[ExtractionItem] = Field(default_factory=list)
    unrecognized: list[UnrecognizedItem] = Field(default_factory=list)
    cross_references: list[CrossReferenceItem] = Field(default_factory=list)
    # Deterministic attribution results
    attributed_elements: list[str] = Field(
        default_factory=list
    )  # Element item IDs (as strings)
    attribution_status: str = "pending"  # matched, no_elements, unmatched_type, pending

    model_config = {"from_attributes": True}


class SectionExtraction(BaseModel):
    """Complete extraction result for a single spec section.

    In multi-pass mode (v2), results are organized by noun. The flat
    extractions/unrecognized/cross_references lists are still populated
    for backward compatibility and contain aggregated results across all nouns.
    """

    section_number: str
    status: str = "extracted"  # extracted, failed, partial
    error: str | None = None  # If status == failed
    # Multi-pass (v2): noun-organized results
    pass1_response: dict | None = None  # Raw Pass 1 LLM output (audit)
    nouns: list[NounExtraction] = Field(
        default_factory=list
    )  # Per-noun extraction results
    # Aggregated flat lists (backward-compatible with v1 consumers)
    extractions: list[ExtractionItem] = Field(default_factory=list)
    unrecognized: list[UnrecognizedItem] = Field(default_factory=list)
    cross_references: list[CrossReferenceItem] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ─── API Request Models ─────────────────────────────────────────


class ExtractRequest(BaseModel):
    """Request body for POST /api/v1/spec/extract."""

    specification_id: uuid.UUID  # Specification item
    preprocess_batch_id: uuid.UUID  # WP-16 batch (must be confirmed)
    context_id: uuid.UUID  # Milestone / issuance context
    section_numbers: list[str] | None = None  # Optional: specific sections only

    model_config = {"from_attributes": True}


# ─── API Response Models ────────────────────────────────────────


class ExtractResponse(BaseModel):
    """Response from POST /api/v1/spec/extract."""

    batch_id: uuid.UUID
    status: str  # "extracting" or "extracted"
    sections_total: int
    message: str = "Extraction started"

    model_config = {"from_attributes": True}


class CrossReferenceReviewItem(BaseModel):
    """Cross-reference with navigability info for the review UI."""

    section_number: str
    relationship: str
    source_text: str = ""
    navigable: bool = False  # True if section exists in graph
    section_item_id: uuid.UUID | None = None  # If navigable

    model_config = {"from_attributes": True}


class NounExtractionReview(BaseModel):
    """Noun-level review data within a section."""

    noun_phrase: str
    matched_type: str | None = None
    qualifiers: dict[str, str] = Field(default_factory=dict)
    context: str = ""
    extractions: list[ExtractionItem] = Field(default_factory=list)
    unrecognized: list[UnrecognizedItem] = Field(default_factory=list)
    cross_references: list[CrossReferenceReviewItem] = Field(default_factory=list)
    attributed_elements: list[str] = Field(default_factory=list)
    attribution_status: str = "pending"

    model_config = {"from_attributes": True}


class SectionExtractionReview(BaseModel):
    """Extraction review data for a single section."""

    section_number: str
    section_title: str | None = None
    status: str  # extracted, failed, partial
    # Multi-pass (v2): noun-organized review
    nouns: list[NounExtractionReview] = Field(default_factory=list)
    # Aggregated flat lists (backward-compatible)
    extractions: list[ExtractionItem] = Field(default_factory=list)
    unrecognized: list[UnrecognizedItem] = Field(default_factory=list)
    cross_references: list[CrossReferenceReviewItem] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ExtractionReviewResponse(BaseModel):
    """Response from GET /api/v1/spec/extract/{batch_id}/review."""

    batch_id: uuid.UUID
    status: str
    specification_name: str | None = None
    context_name: str | None = None  # Milestone name
    sections: list[SectionExtractionReview] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ─── Confirmation Models ────────────────────────────────────────


class ExtractionDecision(BaseModel):
    """User decision on a single extracted property value."""

    property: str
    element_type: str
    action: Literal["confirm", "correct", "reject"]
    corrected_value: str | None = None  # Required if action == "correct"

    model_config = {"from_attributes": True}


class UnrecognizedDecision(BaseModel):
    """User decision on an unrecognized term."""

    term: str
    action: Literal["skip", "add_as_property"]
    property_name: str | None = None  # Required if add_as_property
    target_types: list[str] | None = None  # Required if add_as_property
    data_type: str | None = None  # Defaults to "string"

    model_config = {"from_attributes": True}


class NounDecision(BaseModel):
    """User decision on a noun's type matching and attribution."""

    noun_phrase: str
    action: Literal["confirm", "retype", "split", "skip"] = "confirm"
    corrected_type: str | None = None  # If action == "retype"
    corrected_qualifiers: dict[str, str] | None = None  # If action == "retype"

    model_config = {"from_attributes": True}


class SectionConfirmation(BaseModel):
    """User confirmation for a single section's extractions."""

    section_number: str
    # Noun-level decisions (v2)
    noun_decisions: list[NounDecision] = Field(default_factory=list)
    # Property-level decisions (applied per-noun or globally)
    extraction_decisions: list[ExtractionDecision] = Field(default_factory=list)
    unrecognized_decisions: list[UnrecognizedDecision] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ExtractionConfirmRequest(BaseModel):
    """Request body for POST /api/v1/spec/extract/{batch_id}/confirm."""

    confirmations: list[SectionConfirmation]

    model_config = {"from_attributes": True}


class ExtractionConfirmResponse(BaseModel):
    """Response from POST /api/v1/spec/extract/{batch_id}/confirm."""

    batch_id: uuid.UUID
    status: str  # "confirmed"
    extractions_confirmed: int
    extractions_corrected: int
    extractions_rejected: int
    properties_promoted: int  # New PropertyDefs created
    message: str = "Extractions confirmed"

    model_config = {"from_attributes": True}


# ─── Batch Status ───────────────────────────────────────────────


class ExtractionBatchStatus(BaseModel):
    """Response from GET /api/v1/spec/extract/{batch_id}."""

    batch_id: uuid.UUID
    status: str
    specification_item_id: str | None = None
    preprocess_batch_id: str | None = None
    context_id: str | None = None
    sections_total: int | None = None
    sections_extracted: int | None = None
    sections_failed: int | None = None

    model_config = {"from_attributes": True}
