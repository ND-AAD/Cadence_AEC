"""Tests for identifier and value normalization."""

from decimal import Decimal

import pytest

from app.services.normalization import (
    normalize_identifier,
    normalize_dimension_to_inches,
    normalize_numeric,
    values_match,
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
        assert normalize_dimension_to_inches("36") == Decimal("36")

    def test_not_a_dimension(self):
        assert normalize_dimension_to_inches("paint") is None

    def test_empty(self):
        assert normalize_dimension_to_inches("") is None


class TestValuesMatch:
    def test_same_string(self):
        assert values_match("paint", "paint") is True

    def test_case_insensitive(self):
        assert values_match("Paint", "PAINT") is True

    def test_different_strings(self):
        assert values_match("paint", "stain") is False

    def test_numeric_match(self):
        assert values_match("36", "36.0") is True

    def test_dimension_match(self):
        assert values_match("3'-0\"", "36", property_name="width") is True

    def test_dimension_mismatch(self):
        assert values_match("3'-6\"", "36", property_name="width") is False

    def test_none_both(self):
        assert values_match(None, None) is True

    def test_none_one(self):
        assert values_match("paint", None) is False
        assert values_match(None, "paint") is False

    def test_whitespace_normalization(self):
        assert values_match("  paint  ", "paint") is True
