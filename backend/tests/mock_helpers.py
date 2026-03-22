"""
Shared test mock helpers for multi-pass extraction testing.
"""

import json


def make_multi_pass_mock(extractions_response: str):
    """
    Create a multi-pass-aware mock LLM caller.

    Detects whether the prompt is Pass 1 (noun identification) or
    Pass 2 (per-noun extraction) and returns the appropriate JSON.

    The noun identification pass returns nouns derived from the extraction
    data's element_types so that Pass 2 gets called once per type with
    the original extraction response format.
    """
    parsed = json.loads(extractions_response)
    section_number = parsed.get("section_number", "08 11 00")

    # Build noun identification response from the extraction data
    element_types = set()
    for ext in parsed.get("extractions", []):
        et = ext.get("element_type")
        if et:
            element_types.add(et)

    nouns = []
    for et in element_types or {"door"}:
        nouns.append(
            {
                "noun_phrase": f"{et}s",
                "matched_type": et,
                "qualifiers": {},
                "context": f"Section discusses {et}s",
            }
        )

    noun_response = json.dumps(
        {
            "section_number": section_number,
            "nouns": nouns,
        }
    )

    async def _caller(prompt: str) -> str:
        # Pass 1: noun identification
        if (
            "identify what things" in prompt.lower()
            or "products, assemblies, components" in prompt.lower()
        ):
            return noun_response
        # Pass 2: per-noun extraction — return the full extraction response
        return extractions_response

    return _caller


def make_multi_pass_mock_error():
    """Mock that raises on any LLM call (tests error handling)."""

    async def _caller(prompt: str) -> str:
        raise RuntimeError("API connection failed")

    return _caller
