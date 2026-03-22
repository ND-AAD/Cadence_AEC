"""Tests for identifier and value normalization — WP-6 + WP-6b."""

from decimal import Decimal

import pytest

from app.services.normalization import (
    normalize_identifier,
    normalize_dimension_to_inches,
    normalize_dimension_to_mm,
    normalize_numeric,
    detect_dimension_system,
    build_snapshot_properties,
    values_match,
    DEFAULT_TOLERANCE_MM,
)


class TestNormalizeIdentifier:
    def test_basic(self):
        assert normalize_identifier("Door 101") == "door 101"

    def test_extra_whitespace(self):
        assert normalize_identifier("  Room   203  ") == "room 203"

    def test_case(self):
        assert normalize_identifier("DOOR 101") == "door 101"

    def test_mixed(self):
        assert normalize_identifier("  DR-101  ") == "dr-101"


class TestDimensionNormalization:
    """Legacy tests for normalize_dimension_to_inches (backward compat)."""

    def test_feet_inches(self):
        assert normalize_dimension_to_inches("3'-0\"") == Decimal("36")

    def test_feet_inches_no_space(self):
        assert normalize_dimension_to_inches("3'0\"") == Decimal("36")

    def test_feet_inches_with_space(self):
        assert normalize_dimension_to_inches("3' - 0\"") == Decimal("36")

    def test_feet_inches_mixed(self):
        assert normalize_dimension_to_inches("3'-6\"") == Decimal("42")

    def test_inches_only_quote(self):
        assert normalize_dimension_to_inches("36\"") == Decimal("36")

    def test_inches_only_text(self):
        assert normalize_dimension_to_inches("36 in") == Decimal("36")

    def test_feet_only(self):
        assert normalize_dimension_to_inches("3'") == Decimal("36")

    def test_feet_text(self):
        assert normalize_dimension_to_inches("3 ft") == Decimal("36")

    def test_plain_number(self):
        # WP-6b: bare numbers are now mm (canonical). 36mm ÷ 25.4 = ~1.417"
        result = normalize_dimension_to_inches("36")
        assert result == Decimal("36") / Decimal("25.4")

    def test_not_a_dimension(self):
        assert normalize_dimension_to_inches("paint") is None

    def test_empty(self):
        assert normalize_dimension_to_inches("") is None


class TestDimensionToMm:
    """WP-6b: Canonical mm normalization."""

    # Imperial patterns
    def test_feet_inches_to_mm(self):
        assert normalize_dimension_to_mm("3'-0\"") == Decimal("914.4")

    def test_seven_feet_to_mm(self):
        assert normalize_dimension_to_mm("7'-0\"") == Decimal("2133.6")

    def test_feet_inches_mixed_to_mm(self):
        assert normalize_dimension_to_mm("3'-6\"") == Decimal("1066.8")

    def test_inches_quote_to_mm(self):
        assert normalize_dimension_to_mm('36"') == Decimal("914.4")

    def test_feet_only_to_mm(self):
        assert normalize_dimension_to_mm("3'") == Decimal("914.4")

    # Fraction support
    def test_fraction_half(self):
        result = normalize_dimension_to_mm('3\'-6 1/2"')
        expected = Decimal("42.5") * Decimal("25.4")
        assert result == expected

    def test_fraction_three_quarter(self):
        result = normalize_dimension_to_mm('3\'-0 3/4"')
        expected = Decimal("36.75") * Decimal("25.4")
        assert result == expected

    # Metric patterns
    def test_mm(self):
        assert normalize_dimension_to_mm("1200mm") == Decimal("1200")

    def test_cm(self):
        assert normalize_dimension_to_mm("120cm") == Decimal("1200")

    def test_m(self):
        assert normalize_dimension_to_mm("1.2m") == Decimal("1200")

    def test_mm_lowercase(self):
        assert normalize_dimension_to_mm("914mm") == Decimal("914")

    def test_cm_uppercase(self):
        assert normalize_dimension_to_mm("120CM") == Decimal("1200")

    # Bare number → mm (canonical)
    def test_bare_number(self):
        assert normalize_dimension_to_mm("36") == Decimal("36")

    def test_not_a_dimension(self):
        assert normalize_dimension_to_mm("paint") is None

    def test_empty(self):
        assert normalize_dimension_to_mm("") is None


class TestDimensionSystemDetection:
    """WP-6b: Per-value dimension system detection."""

    def test_imperial_feet_inches(self):
        assert detect_dimension_system("3'-0\"") == "imperial"

    def test_imperial_inches(self):
        assert detect_dimension_system('36"') == "imperial"

    def test_imperial_ft(self):
        assert detect_dimension_system("3 ft") == "imperial"

    def test_metric_mm(self):
        assert detect_dimension_system("1200mm") == "metric"

    def test_metric_cm(self):
        assert detect_dimension_system("120cm") == "metric"

    def test_metric_m(self):
        assert detect_dimension_system("1.2m") == "metric"

    def test_unknown_bare(self):
        assert detect_dimension_system("36") == "unknown"

    def test_unknown_empty(self):
        assert detect_dimension_system("") == "unknown"


class TestValuesMatch:
    def test_same_string(self):
        assert values_match("paint", "paint") is True

    def test_case_insensitive(self):
        assert values_match("Paint", "PAINT") is True

    def test_different_strings(self):
        assert values_match("paint", "stain") is False

    def test_numeric_match(self):
        assert values_match("36", "36.0") is True

    def test_dimension_match_imperial_to_mm(self):
        """WP-6b: 3'-0\" (914.4mm) vs 914mm → match within 1mm tolerance."""
        assert values_match("3'-0\"", "914mm", property_name="width") is True

    def test_dimension_match_imperial_to_imperial(self):
        """3'-0\" vs 36\" should match (both 914.4mm)."""
        assert values_match("3'-0\"", '36"', property_name="width") is True

    def test_dimension_mismatch(self):
        """3'-6\" (1066.8mm) vs 900mm → no match."""
        assert values_match("3'-6\"", "900mm", property_name="width") is False

    def test_dimension_tolerance_within(self):
        """914mm vs 3'-0\" (914.4mm) → delta 0.4mm < 1mm tolerance → match."""
        assert values_match("914mm", "3'-0\"", property_name="width") is True

    def test_dimension_tolerance_exceed(self):
        """900mm vs 3'-0\" (914.4mm) → delta 14.4mm > 1mm tolerance → no match."""
        assert values_match("900mm", "3'-0\"", property_name="width") is False

    def test_none_both(self):
        assert values_match(None, None) is True

    def test_none_one(self):
        assert values_match("paint", None) is False
        assert values_match(None, "paint") is False

    def test_whitespace_normalization(self):
        assert values_match("  paint  ", "paint") is True


class TestDualStorage:
    """WP-6b: build_snapshot_properties dual storage."""

    def test_dimension_property_gets_dual(self):
        props = build_snapshot_properties(
            {"width": '3\'-0"', "material": "HM"},
            {"width"},
        )
        assert props["width"] == "914.4"
        assert props["width_raw"] == '3\'-0"'
        assert props["material"] == "HM"
        assert "material_raw" not in props

    def test_non_dimension_no_raw(self):
        props = build_snapshot_properties(
            {"fire_rating": "90 min"},
            {"width"},
        )
        assert props["fire_rating"] == "90 min"
        assert "fire_rating_raw" not in props

    def test_unparseable_dimension_stored_as_is(self):
        props = build_snapshot_properties(
            {"width": "TBD"},
            {"width"},
        )
        assert props["width"] == "TBD"
        assert "width_raw" not in props
