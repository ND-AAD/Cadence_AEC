"""
AEC column alias presets for auto-mapping.

Three-layer alias resolution (Section 3.2 of WP-6b spec):
  1. User corrections (highest priority) — stored in project properties
  2. Type-derived matching — from PropertyDef labels in type_config.py
  3. AEC presets (this module) — seeded from Delta Project, expanded for v6.2

Aliases map raw column header text (as found in real-world documents)
to canonical Cadence property names.

Organized by domain (door, room, etc.) so new domains can be added
as dictionaries. The auto-mapping service loads and merges all
alias dictionaries, with type-specific aliases taking priority
when the target type is known.
"""

# ─── Identifier Aliases ─────────────────────────────────────────
# Column names that indicate the identifier column (not mapped to
# a property — used to detect which column holds item identifiers).

IDENTIFIER_ALIASES: set[str] = {
    "mark", "door_mark", "door_number", "door_no", "door_#",
    "number", "no", "no.", "#", "id", "identifier",
    "item_no", "item_number", "ref", "reference",
    "room_number", "room_no", "room_#",
}


# ─── Property Aliases by Domain ─────────────────────────────────

DOOR_PROPERTY_ALIASES: dict[str, str] = {
    # Dimensions
    "w": "width", "door_width": "width", "clear_width": "width",
    "h": "height", "door_height": "height", "clear_height": "height",
    "t": "thickness", "door_thickness": "thickness", "thk": "thickness",

    # Fire rating
    "fr": "fire_rating", "fire_rate": "fire_rating",
    "rating": "fire_rating", "f.r.": "fire_rating",
    "fire_rated": "fire_rating", "fire_resistance": "fire_rating",

    # Type
    "door_type": "type", "dt": "type", "style": "type",

    # Location
    "room": "location", "room_number": "location",
    "room_name": "location", "rm": "location",
    "from": "location", "to": "location_to",

    # Hardware
    "hw": "hardware_set", "hw_set": "hardware_set",
    "hardware": "hardware_set", "hardware_group": "hardware_set",
    "hdw": "hardware_set", "hd_set": "hardware_set",

    # Frame
    "frame": "frame_type", "frame_material": "frame_material",
    "frame_finish": "frame_finish", "frame_type": "frame_type",
    "frame_detail": "frame_detail",

    # Finish
    "finish": "finish", "fnsh": "finish", "door_finish": "finish",
    "surface": "finish", "surface_finish": "finish",

    # Glass/Glazing
    "glass": "glazing", "glazing": "glazing", "gl": "glazing",
    "glass_type": "glazing", "lite": "glazing",
    "vision_panel": "glazing", "vision": "glazing",

    # Swing/Handing
    "swing": "swing", "hand": "handing", "handing": "handing",
    "lh": "handing", "rh": "handing",

    # Closer
    "closer": "closer", "door_closer": "closer", "cl": "closer",

    # Lock
    "lock": "lock_function", "lock_function": "lock_function",
    "lockset": "lock_function", "lock_type": "lock_function",

    # Level
    "floor": "level", "story": "level", "flr": "level",

    # Rebate (also called rabbet)
    "rebate_width": "rebate_width", "rabbet_width": "rebate_width",
    "rebate_height": "rebate_height", "rabbet_height": "rebate_height",
    "rebate_w": "rebate_width", "rebate_h": "rebate_height",

    # Panel
    "panel": "panel_type", "panel_type": "panel_type",

    # Material
    "door_material": "material", "mat": "material",
    "mtl": "material", "mat.": "material",
}


ROOM_PROPERTY_ALIASES: dict[str, str] = {
    "room_name": "name", "rm_name": "name",
    "room_number": "number", "rm_no": "number", "rm_#": "number",
    "sf": "area", "sqft": "area", "sq_ft": "area", "area_sf": "area",
    "floor_finish": "finish_floor", "flr_finish": "finish_floor",
    "wall_finish": "finish_wall", "wl_finish": "finish_wall",
    "ceiling_finish": "finish_ceiling", "clg_finish": "finish_ceiling",
    "clg_height": "ceiling_height", "ceiling_ht": "ceiling_height",
}


# ─── Ignored Column Patterns ────────────────────────────────────
# Columns matching these patterns are skipped during mapping.

IGNORED_PATTERNS: set[str] = {
    "unnamed", "none", "n/a", "blank", "empty",
    "table", "sheet", "page", "row", "col",
    "notes",  # Notes columns are captured separately
}


# ─── Domain Registry ────────────────────────────────────────────
# Maps item type names to their domain-specific alias dictionaries.
# The auto-mapping service uses this to apply type-specific aliases
# when the target type is known.

DOMAIN_ALIASES: dict[str, dict[str, str]] = {
    "door": DOOR_PROPERTY_ALIASES,
    "room": ROOM_PROPERTY_ALIASES,
}


# ─── AEC Header Keywords ────────────────────────────────────────
# Used by header row detection to score rows. A row containing
# these keywords is more likely to be a header row.

HEADER_KEYWORDS: set[str] = {
    "number", "type", "door", "height", "width", "level",
    "location", "fire", "rating", "finish", "material",
    "frame", "hardware", "glass", "thickness", "mark",
    "handing", "swing", "closer", "lock", "glazing",
    "panel", "rebate", "room", "area", "ceiling",
}


def get_all_aliases() -> dict[str, str]:
    """
    Merge all domain alias dictionaries into a single lookup.

    When there's a collision between domains, later domains overwrite
    earlier ones. This is acceptable because when the target type is
    known, domain-specific aliases should be used instead.
    """
    merged: dict[str, str] = {}
    for domain_aliases in DOMAIN_ALIASES.values():
        merged.update(domain_aliases)
    return merged


def get_aliases_for_type(type_name: str) -> dict[str, str]:
    """
    Get the alias dictionary for a specific item type.

    Falls back to the merged global aliases if no domain-specific
    aliases exist for the type.
    """
    return DOMAIN_ALIASES.get(type_name, get_all_aliases())


def clean_column_name(raw: str) -> str:
    """
    Clean and normalize a raw column header for alias lookup.

    Ported from Delta Project ExcelProcessor._clean_column_names.
    - Lowercase
    - Replace spaces, hyphens, special chars with underscores
    - Strip parentheses, periods, slashes
    - Collapse multiple underscores
    - Strip leading/trailing underscores
    """
    if not raw or not str(raw).strip():
        return "unnamed"

    cleaned = (
        str(raw)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace("\\", "_")
    )

    # Don't strip periods from abbreviations like "no." or "f.r."
    # but do strip trailing periods
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]

    # Collapse multiple underscores
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")

    # Strip leading/trailing underscores
    cleaned = cleaned.strip("_")

    if not cleaned or "unnamed" in cleaned:
        return "unnamed"

    return cleaned


def is_ignored_column(cleaned_name: str) -> bool:
    """Check if a cleaned column name should be ignored."""
    return cleaned_name in IGNORED_PATTERNS or any(
        pattern in cleaned_name for pattern in IGNORED_PATTERNS
    )
