"""
Identifier and value normalization utilities.

Used for import matching and conflict comparison.
Normalizations are composable — each is a small function
that can be chained.
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


# ─── Dimension Normalization ──────────────────────────────────

# Common dimension patterns in AEC:
#   3'-0"      → 36 (inches)
#   3'0"       → 36
#   3' - 0"    → 36
#   36"        → 36
#   36 in      → 36
#   3 ft       → 36
#   3'         → 36
#   3'-6"      → 42

_FEET_INCHES_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*['\u2018\u2019]\s*"
    r"[-\u2013\s]*"
    r"(\d+(?:\.\d+)?)\s*[\"\u201c\u201d]?\s*$"
)

_FEET_ONLY_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*"
    r"(?:['\u2018\u2019]\s*|ft\.?\s*|feet\s*)$",
    re.IGNORECASE,
)

_INCHES_ONLY_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*"
    r"(?:[\"\u201c\u201d]|in\.?|inch(?:es)?)\s*$",
    re.IGNORECASE,
)


def normalize_dimension_to_inches(value: str) -> Decimal | None:
    """
    Parse AEC dimension strings to inches.

    Returns None if the value doesn't look like a dimension.
    """
    value = value.strip()
    if not value:
        return None

    # Feet and inches: 3'-6"
    m = _FEET_INCHES_PATTERN.match(value)
    if m:
        feet = Decimal(m.group(1))
        inches = Decimal(m.group(2))
        return feet * 12 + inches

    # Feet only: 3' or 3 ft
    m = _FEET_ONLY_PATTERN.match(value)
    if m:
        return Decimal(m.group(1)) * 12

    # Inches only: 36" or 36 in
    m = _INCHES_ONLY_PATTERN.match(value)
    if m:
        return Decimal(m.group(1))

    # Plain number — assume inches
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


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


# ─── Value Comparison ─────────────────────────────────────────

def values_match(val_a: str | None, val_b: str | None, property_name: str = "") -> bool:
    """
    Compare two values with normalization.

    Uses dimension normalization for known dimension properties,
    case-insensitive comparison otherwise.
    """
    if val_a is None and val_b is None:
        return True
    if val_a is None or val_b is None:
        return False

    a = str(val_a).strip()
    b = str(val_b).strip()

    # Try dimension comparison for dimension-like properties
    dimension_props = {"width", "height", "depth", "thickness", "length", "area"}
    if property_name.lower() in dimension_props:
        dim_a = normalize_dimension_to_inches(a)
        dim_b = normalize_dimension_to_inches(b)
        if dim_a is not None and dim_b is not None:
            return dim_a == dim_b

    # Try numeric comparison
    try:
        num_a = Decimal(a)
        num_b = Decimal(b)
        return num_a == num_b
    except InvalidOperation:
        pass

    # Fall back to normalized string comparison
    return normalize_case(normalize_whitespace(a)) == normalize_case(normalize_whitespace(b))
