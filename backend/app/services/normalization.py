"""
Identifier and value normalization utilities — WP-6 + WP-6b.

Used for import matching and conflict comparison.
Normalizations are composable — each is a small function
that can be chained.

WP-6b expands this module:
  - Canonical unit: mm (not inches) for all dimension storage
  - Metric parsing: mm, cm, m with auto-detection
  - Fraction support: 3'-6 1/2" → 1079.5mm
  - Per-value dimension system auto-detection (no project-level unit setting)
  - Tolerance-based comparison for dimensions
  - Dual storage: canonical mm + raw source string via _raw suffix
"""

import re
from decimal import Decimal, InvalidOperation


def normalize_whitespace(value: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", value.strip())


def normalize_case(value: str) -> str:
    """Lowercase for case-insensitive comparison."""
    return value.lower()


def normalize_identifier(value: str) -> str:
    """
    Standard identifier normalization chain.
    'DOOR  101' → 'door 101'
    '  Room   203  ' → 'room 203'
    """
    return normalize_case(normalize_whitespace(value))


# ─── Dimension Normalization (WP-6b: canonical mm) ──────────────

# Imperial patterns — feet and inches with optional fractions
# Matches: 3'-0", 3' - 0", 3'-6 1/2", 3'0", 3'-0 3/4"
_FEET_INCHES_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*['\u2018\u2019]\s*"
    r"[-\u2013\s]*"
    r"(\d+(?:\.\d+)?)"
    r"(?:\s+(\d+)/(\d+))?"       # optional fraction: 1/2, 3/4
    r"\s*[\"\u201c\u201d]?\s*$"
)

_FEET_ONLY_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*"
    r"(?:['\u2018\u2019]\s*|ft\.?\s*|feet\s*)$",
    re.IGNORECASE,
)

_INCHES_ONLY_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)"
    r"(?:\s+(\d+)/(\d+))?"       # optional fraction
    r"\s*(?:[\"\u201c\u201d]|in\.?|inch(?:es)?)\s*$",
    re.IGNORECASE,
)

# Metric patterns
_MM_PATTERN = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)\s*mm\s*$",
    re.IGNORECASE,
)

_CM_PATTERN = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)\s*cm\s*$",
    re.IGNORECASE,
)

_M_PATTERN = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)\s*m\s*$",
    re.IGNORECASE,
)


def _parse_decimal(s: str) -> Decimal:
    """Parse a numeric string, handling comma as decimal separator."""
    return Decimal(s.replace(",", "."))


def detect_dimension_system(value: str) -> str:
    """
    Detect the dimension system of a value string.

    Returns: 'imperial', 'metric', or 'unknown'
    Per-value detection, not per-project (WP-6b spec Section 3.7.4).
    """
    value = str(value).strip()
    if not value:
        return "unknown"

    # Check for imperial indicators: ' " ft in
    if "'" in value or "\u2018" in value or "\u2019" in value:
        return "imperial"
    if '"' in value or "\u201c" in value or "\u201d" in value:
        return "imperial"
    if re.search(r'\b(ft|feet|in|inch|inches)\b', value, re.IGNORECASE):
        return "imperial"

    # Check for metric indicators: mm, cm, m
    if re.search(r'(mm|cm)', value, re.IGNORECASE):
        return "metric"
    # Match 'm' only when preceded by digits (to avoid false positives)
    if re.search(r'\d\s*m\s*$', value, re.IGNORECASE):
        return "metric"

    return "unknown"


def normalize_dimension_to_mm(value: str) -> Decimal | None:
    """
    Parse any AEC dimension string to canonical mm.

    WP-6b canonical unit. Returns None if the value doesn't look
    like a dimension.

    Supports:
      Imperial: 3'-0", 3'-6 1/2", 3'0", 36", 3 ft, 3'
      Metric:   1200mm, 120cm, 1.2m, 1200
      Bare numbers: treated as mm (canonical unit)
    """
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None

    # ── Metric patterns ──────────────────────────────────────────

    m = _MM_PATTERN.match(value)
    if m:
        return _parse_decimal(m.group(1))

    m = _CM_PATTERN.match(value)
    if m:
        return _parse_decimal(m.group(1)) * 10

    m = _M_PATTERN.match(value)
    if m:
        return _parse_decimal(m.group(1)) * 1000

    # ── Imperial patterns ────────────────────────────────────────

    # Feet and inches: 3'-6", 3'-6 1/2"
    m = _FEET_INCHES_PATTERN.match(value)
    if m:
        feet = Decimal(m.group(1))
        inches = Decimal(m.group(2))
        if m.group(3) and m.group(4):
            inches += Decimal(m.group(3)) / Decimal(m.group(4))
        total_inches = feet * 12 + inches
        return total_inches * Decimal("25.4")

    # Feet only: 3' or 3 ft
    m = _FEET_ONLY_PATTERN.match(value)
    if m:
        feet = Decimal(m.group(1))
        return feet * 12 * Decimal("25.4")

    # Inches only: 36" or 36 in, with optional fraction
    m = _INCHES_ONLY_PATTERN.match(value)
    if m:
        inches = Decimal(m.group(1))
        if m.group(2) and m.group(3):
            inches += Decimal(m.group(2)) / Decimal(m.group(3))
        return inches * Decimal("25.4")

    # ── Bare number → mm (canonical) ─────────────────────────────
    try:
        return _parse_decimal(value)
    except InvalidOperation:
        return None


def normalize_dimension_to_inches(value: str) -> Decimal | None:
    """
    Parse AEC dimension strings to inches.

    Legacy function preserved for backward compatibility.
    Internally converts via mm and back to inches.
    Returns None if the value doesn't look like a dimension.
    """
    mm = normalize_dimension_to_mm(value)
    if mm is None:
        return None
    return mm / Decimal("25.4")


def normalize_numeric(value: str) -> str:
    """
    Normalize numeric strings for comparison.
    Strips trailing zeros and normalizes representation.
    """
    try:
        d = Decimal(value.strip())
        return str(d.normalize())
    except InvalidOperation:
        return value.strip()


# ─── Value Comparison (WP-6b: tolerance-based) ──────────────────

# Default tolerance in mm. 1mm catches genuine disagreements
# while ignoring rounding between unit systems.
# e.g., 3'-0" = 914.4mm vs 914mm → delta 0.4mm < 1mm → match.
DEFAULT_TOLERANCE_MM = Decimal("1.0")


def values_match(
    val_a: str | None,
    val_b: str | None,
    property_name: str = "",
    tolerance_mm: Decimal | None = None,
) -> bool:
    """
    Compare two values with normalization.

    WP-6b: uses tolerance-based comparison for dimension properties.
    Tolerance defaults to 1mm (±0.039").

    For dimension properties: normalizes both values to mm, then
    compares with tolerance.
    For numeric properties: exact decimal comparison.
    Otherwise: case-insensitive string comparison.
    """
    if val_a is None and val_b is None:
        return True
    if val_a is None or val_b is None:
        return False

    a = str(val_a).strip()
    b = str(val_b).strip()

    if tolerance_mm is None:
        tolerance_mm = DEFAULT_TOLERANCE_MM

    # Try dimension comparison for dimension-like properties
    dimension_props = {
        "width", "height", "depth", "thickness", "length",
        "rebate_width", "rebate_height", "ceiling_height",
    }
    if property_name.lower() in dimension_props:
        dim_a = normalize_dimension_to_mm(a)
        dim_b = normalize_dimension_to_mm(b)
        if dim_a is not None and dim_b is not None:
            return abs(dim_a - dim_b) <= tolerance_mm

    # Try numeric comparison
    try:
        num_a = Decimal(a)
        num_b = Decimal(b)
        return num_a == num_b
    except InvalidOperation:
        pass

    # Fall back to normalized string comparison
    return normalize_case(normalize_whitespace(a)) == normalize_case(normalize_whitespace(b))


# ─── Dual Storage Helpers (WP-6b: canonical + raw) ──────────────

def build_snapshot_properties(
    raw_properties: dict[str, str],
    dimension_property_names: set[str],
) -> dict[str, str]:
    """
    Build snapshot properties with dual storage for dimension values.

    For dimension properties (those with a unit):
      - property_name: canonical mm value (for comparison)
      - property_name_raw: raw source string (for display)

    For non-dimension properties:
      - property_name: value as-is (no _raw needed)

    Args:
        raw_properties: Property name → raw value from the parsed file row
        dimension_property_names: Set of property names that are dimension types
                                   (derived from PropertyDef where unit is set)

    Returns:
        dict with canonical + raw properties for dimensions, as-is for others
    """
    result: dict[str, str] = {}

    for prop_name, raw_value in raw_properties.items():
        if raw_value is None:
            continue

        raw_str = str(raw_value).strip()
        if not raw_str:
            continue

        if prop_name in dimension_property_names:
            # Dimension property: normalize to mm for comparison, keep raw for display
            mm_value = normalize_dimension_to_mm(raw_str)
            if mm_value is not None:
                result[prop_name] = str(mm_value)
                result[f"{prop_name}_raw"] = raw_str
            else:
                # Couldn't parse as dimension — store as-is
                result[prop_name] = raw_str
        else:
            # Non-dimension: store as-is
            result[prop_name] = raw_str

    return result
