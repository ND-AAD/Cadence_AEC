"""Tests for auto-mapping with dynamic types (WP-DYN-3).

Verifies that detect_target_type, build_property_mapping, and propose_mapping
accept an optional importable_types parameter, using custom TypeConfig objects
instead of the global ITEM_TYPES registry when provided.
"""

import csv
import io

from app.core.type_config import PropertyDef, TypeConfig


# ─── Helper: create test types ────────────────────────────────


def make_test_type(name, properties):
    """Create a minimal TypeConfig for testing."""
    return TypeConfig(
        name=name,
        label=name.replace("_", " ").title(),
        plural_label=f"{name.replace('_', ' ').title()}s",
        category="spatial",
        properties=[
            PropertyDef(
                name=p["name"],
                label=p.get("label", p["name"].replace("_", " ").title()),
                aliases=tuple(p["aliases"]) if p.get("aliases") else None,
            )
            for p in properties
        ],
    )


HARDWARE_TYPE = make_test_type(
    "hardware_set",
    [
        {"name": "mark", "label": "Mark", "aliases": ["hardware_mark", "hw_mark"]},
        {"name": "manufacturer", "label": "Manufacturer", "aliases": ["mfr", "mfg"]},
        {"name": "series", "label": "Series"},
        {"name": "finish", "label": "Finish"},
    ],
)


# ─── detect_target_type with custom types ─────────────────────


def test_detect_target_type_with_custom_type_list():
    """detect_target_type matches against a provided type list."""
    from app.services.auto_mapping import detect_target_type

    headers = ["Mark", "Manufacturer", "Series", "Finish"]
    target, confidence, _ = detect_target_type(
        headers,
        importable_types=[HARDWARE_TYPE],
    )
    assert target == "hardware_set"
    assert confidence > 0.5


def test_detect_target_type_custom_aliases():
    """Custom type aliases work in detect_target_type."""
    from app.services.auto_mapping import detect_target_type

    headers = ["HW Mark", "MFR", "Series", "Finish"]
    target, confidence, _ = detect_target_type(
        headers,
        importable_types=[HARDWARE_TYPE],
    )
    assert target == "hardware_set"
    assert confidence > 0.5


def test_detect_target_type_without_param_returns_empty():
    """Without importable_types param, get_importable_types() is empty (DYN-0).

    After DYN-0, spatial types are firm vocabulary. The OS-level
    get_importable_types() returns empty. Callers must pass importable_types.
    """
    from app.services.auto_mapping import detect_target_type

    headers = ["Mark", "Width", "Height", "Material", "Fire Rating"]
    target, confidence, _ = detect_target_type(headers)
    # No OS spatial types → no match
    assert target == ""
    assert confidence == 0.0


# ─── build_property_mapping with custom types ─────────────────


def test_build_property_mapping_with_custom_type():
    """build_property_mapping uses properties from the provided type."""
    from app.services.auto_mapping import build_property_mapping

    # Note: "Mark" is a known identifier alias, so it maps to __identifier__
    headers = ["Mark", "Manufacturer", "Series"]
    proposals = build_property_mapping(
        headers,
        target_type="hardware_set",
        importable_types=[HARDWARE_TYPE],
    )

    mapped = {
        p.column_name: p.proposed_property for p in proposals if p.proposed_property
    }
    # "Mark" is recognized as an identifier column (in IDENTIFIER_ALIASES)
    assert mapped.get("Mark") == "__identifier__"
    assert mapped.get("Manufacturer") == "manufacturer"
    assert mapped.get("Series") == "series"


def test_build_property_mapping_custom_aliases():
    """Aliases from custom types work in property mapping."""
    from app.services.auto_mapping import build_property_mapping

    headers = ["HW Mark", "MFR", "Series"]
    proposals = build_property_mapping(
        headers,
        target_type="hardware_set",
        importable_types=[HARDWARE_TYPE],
    )

    mapped = {
        p.column_name: p.proposed_property for p in proposals if p.proposed_property
    }
    assert mapped.get("HW Mark") == "mark"
    assert mapped.get("MFR") == "manufacturer"


# ─── propose_mapping with custom types ────────────────────────


def test_propose_mapping_with_custom_types():
    """propose_mapping accepts importable_types parameter."""
    from app.services.auto_mapping import propose_mapping

    # Create a CSV with hardware set columns
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Mark", "Manufacturer", "Series", "Finish"])
    writer.writerow(["HW-001", "Acme", "Pro", "Brushed"])
    writer.writerow(["HW-002", "Best", "Std", "Polished"])
    csv_bytes = buf.getvalue().encode()

    result = propose_mapping(
        csv_bytes,
        file_type="csv",
        importable_types=[HARDWARE_TYPE],
    )

    assert result.target_item_type == "hardware_set"
    assert result.proposed_config is not None
    assert result.proposed_config.target_item_type == "hardware_set"
