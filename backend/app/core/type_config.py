"""
Item type configuration.

Types are application configuration, not database schema.
Adding a new type requires zero migrations — just an entry here.

Each type defines:
  - display metadata (label, icon, color, render_mode)
  - which properties are expected
  - which connection targets are valid
  - navigation and search behavior
  - conflict detection participation

Implementation notes (spec alignment):
  - Tech spec v6.1 `isTemporal` → code `is_context_type` (role in the triple)
  - `is_source_type` added in implementation (not in original spec)
  - `render_mode` from tech spec: how the scale panel renders items of this type
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PropertyDef:
    """Definition of an expected property on an item type.

    The `aliases` and `normalization` fields support auto-mapping (WP-6b):
      - aliases: alternative column header names that map to this property
      - normalization: default normalization type applied during import
    """

    name: str
    label: str
    data_type: str = "string"  # string, number, boolean, date, enum
    required: bool = False
    enum_values: list[str] | None = None
    unit: str | None = None
    description: str = ""
    # WP-6b: Additional column header names for auto-mapping
    aliases: tuple[str, ...] | None = None
    # WP-6b: Default normalization type (e.g., "dimension", "numeric")
    normalization: str | None = None


@dataclass(frozen=True)
class TypeConfig:
    """Configuration for an item type."""

    name: str
    label: str
    plural_label: str
    category: str  # spatial, document, temporal, workflow, organization
    icon: str = ""
    color: str = ""
    properties: list[PropertyDef] = field(default_factory=list)
    # Item types this type can connect TO (as source)
    valid_targets: list[str] = field(default_factory=list)
    # Whether this type appears in navigation as a drillable node
    navigable: bool = True
    # Whether items of this type can be a snapshot source
    is_source_type: bool = False
    # Whether items of this type can be a snapshot context (milestone)
    # (Tech spec v6.1: `isTemporal`)
    is_context_type: bool = False
    # How to render items of this type in the scale panel
    # Values: "table" (tabular grid), "cards" (visual cards),
    #         "list" (simple list), "timeline" (temporal sequence)
    render_mode: str = "list"
    # Default sort field for items of this type
    default_sort: str = "identifier"
    # Which property names are included in search indexing
    search_fields: list[str] = field(default_factory=list)
    # Whether to exclude this type's snapshots from conflict detection.
    # When True, snapshots from items of this type are not used as
    # comparison sources in cross-source conflict analysis.
    exclude_from_conflicts: bool = False
    # WP-17: MasterFormat divisions that govern this type.
    # Used to assemble extraction vocabulary: Division "08" → doors, windows.
    # Empty tuple means this type is not governed by any MasterFormat division.
    masterformat_divisions: tuple[str, ...] = ()


# ─── Type Registry ─────────────────────────────────────────────

ITEM_TYPES: dict[str, TypeConfig] = {}


def register_type(config: TypeConfig) -> TypeConfig:
    """Register an item type configuration."""
    ITEM_TYPES[config.name] = config
    return config


def get_type_config(type_name: str) -> TypeConfig | None:
    """Look up configuration for a type name."""
    return ITEM_TYPES.get(type_name)


def get_types_by_category(category: str) -> list[TypeConfig]:
    """Get all types in a category."""
    return [t for t in ITEM_TYPES.values() if t.category == category]


def get_conflict_excluded_types() -> set[str]:
    """Get type names that are excluded from conflict detection."""
    return {t.name for t in ITEM_TYPES.values() if t.exclude_from_conflicts}


def get_importable_types() -> list[TypeConfig]:
    """Get item types that have properties defined (candidates for import)."""
    return [
        t for t in ITEM_TYPES.values() if t.properties and t.category in ("spatial",)
    ]


def build_label_map(type_name: str) -> dict[str, str]:
    """
    Build a mapping from lowercased property labels and aliases to property names.

    Used by the auto-mapping service (WP-6b) for Layer 2 matching:
    type-derived matching from PropertyDef labels.

    Returns: dict mapping cleaned label → property name.
    Example: {"fire rating": "fire_rating", "fr": "fire_rating", ...}
    """
    tc = get_type_config(type_name)
    if not tc:
        return {}

    label_map: dict[str, str] = {}
    for prop in tc.properties:
        # Exact label (lowercased)
        label_map[prop.label.lower()] = prop.name
        # Property name itself (already canonical, but useful for matching)
        label_map[prop.name] = prop.name
        # All aliases from the PropertyDef
        if prop.aliases:
            for alias in prop.aliases:
                label_map[alias.lower()] = prop.name

    return label_map


def get_dimension_properties(type_name: str) -> set[str]:
    """Get property names that have a unit set (dimension properties)."""
    tc = get_type_config(type_name)
    if not tc:
        return set()
    return {prop.name for prop in tc.properties if prop.unit}


def get_vocabulary_for_division(division: str) -> dict[str, list[PropertyDef]]:
    """
    Return all PropertyDefs for element types governed by a MasterFormat division.

    WP-17: Used to assemble the extraction vocabulary for a given spec section.
    The division code (e.g., "08") maps to spatial types that declare that
    division in their masterformat_divisions tuple.

    Args:
        division: Two-digit MasterFormat division code (e.g., "08").

    Returns:
        Dict mapping type_name → list of PropertyDef.
        Example: {"door": [PropertyDef(name="material", ...), ...]}
        Empty dict if no types are mapped to the division.
    """
    result: dict[str, list[PropertyDef]] = {}
    for type_name, config in ITEM_TYPES.items():
        if division in config.masterformat_divisions:
            result[type_name] = list(config.properties)
    return result


def get_types_for_division(division: str) -> list[str]:
    """
    Return type names governed by a MasterFormat division.

    WP-17: Convenience function for determining which element types
    are relevant to a given spec section's division.

    Args:
        division: Two-digit MasterFormat division code (e.g., "08").

    Returns:
        List of type names (e.g., ["door", "window"]).
    """
    return [
        config.name
        for config in ITEM_TYPES.values()
        if division in config.masterformat_divisions
    ]


# ─── Organization Types ────────────────────────────────────────

register_type(
    TypeConfig(
        name="project",
        label="Project",
        plural_label="Projects",
        category="organization",
        valid_targets=["building", "schedule", "specification", "milestone", "phase"],
        navigable=True,
        render_mode="cards",
        default_sort="name",
        search_fields=["name"],
    )
)

register_type(
    TypeConfig(
        name="portfolio",
        label="Portfolio",
        plural_label="Portfolios",
        category="organization",
        valid_targets=["project"],
        navigable=True,
        render_mode="cards",
        default_sort="name",
        search_fields=["name"],
    )
)

register_type(
    TypeConfig(
        name="firm",
        label="Firm",
        plural_label="Firms",
        category="organization",
        valid_targets=["portfolio", "project"],
        navigable=True,
        render_mode="cards",
        default_sort="name",
        search_fields=["name"],
    )
)


# ─── Spatial Types ─────────────────────────────────────────────
# REMOVED (DYN-0 flip): building, floor, room, frame, door
# These are now firm vocabulary, seeded from type_starter_catalog.py.
# They live as type_definition items connected to a firm, not in ITEM_TYPES.


# ─── Document Types ────────────────────────────────────────────

register_type(
    TypeConfig(
        name="schedule",
        label="Schedule",
        plural_label="Schedules",
        category="document",
        is_source_type=True,
        valid_targets=["door", "room", "floor"],
        navigable=True,
        render_mode="table",
        default_sort="name",
        search_fields=["name", "document_number", "discipline"],
        properties=[
            PropertyDef("name", "Name", required=True),
            PropertyDef("document_number", "Document Number"),
            PropertyDef("discipline", "Discipline"),
        ],
    )
)

register_type(
    TypeConfig(
        name="specification",
        label="Specification",
        plural_label="Specifications",
        category="document",
        is_source_type=True,
        valid_targets=["door", "room"],
        navigable=True,
        render_mode="list",
        default_sort="section_number",
        search_fields=["name", "section_number", "discipline"],
        properties=[
            PropertyDef("name", "Name", required=True),
            PropertyDef("section_number", "Section Number"),
            PropertyDef("discipline", "Discipline"),
        ],
    )
)

register_type(
    TypeConfig(
        name="drawing",
        label="Drawing",
        plural_label="Drawings",
        category="document",
        is_source_type=True,
        valid_targets=["door", "room", "floor", "building"],
        navigable=True,
        render_mode="list",
        default_sort="sheet_number",
        search_fields=["name", "sheet_number", "discipline"],
        properties=[
            PropertyDef("name", "Name", required=True),
            PropertyDef("sheet_number", "Sheet Number"),
            PropertyDef("discipline", "Discipline"),
        ],
    )
)

register_type(
    TypeConfig(
        name="spec_section",
        label="Specification Section",
        plural_label="Specification Sections",
        category="document",
        valid_targets=["spec_section", "door", "room"],
        navigable=True,
        render_mode="list",
        default_sort="identifier",
        search_fields=["title", "identifier"],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("title", "Title", required=True),
            PropertyDef("division", "Division"),
            PropertyDef(
                "level",
                "Level",
                data_type="number",
                description="0=Division, 1=Group, 2=Section, 3=Subsection",
            ),
        ],
    )
)


# ─── Temporal Types ────────────────────────────────────────────

register_type(
    TypeConfig(
        name="milestone",
        label="Milestone",
        plural_label="Milestones",
        category="temporal",
        is_context_type=True,
        navigable=True,
        render_mode="timeline",
        default_sort="ordinal",
        search_fields=["name"],
        properties=[
            PropertyDef("name", "Name", required=True),
            PropertyDef(
                "ordinal",
                "Ordinal",
                data_type="number",
                required=True,
                description="Determines sequence: 100, 200, 300...",
            ),
            PropertyDef("date", "Date", data_type="date"),
            PropertyDef("phase", "Phase"),
        ],
    )
)

register_type(
    TypeConfig(
        name="phase",
        label="Phase",
        plural_label="Phases",
        category="temporal",
        valid_targets=["milestone"],
        navigable=True,
        render_mode="timeline",
        default_sort="name",
        search_fields=["name", "abbreviation"],
        properties=[
            PropertyDef("name", "Name", required=True),
            PropertyDef("abbreviation", "Abbreviation"),
        ],
    )
)

register_type(
    TypeConfig(
        name="import_batch",
        label="Import Batch",
        plural_label="Import Batches",
        category="temporal",
        navigable=False,
        render_mode="list",
        default_sort="created_at",
        search_fields=["filename"],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("filename", "Filename", required=True),
            PropertyDef("row_count", "Row Count", data_type="number"),
            PropertyDef(
                "status",
                "Status",
                data_type="enum",
                enum_values=["pending", "processing", "completed", "failed"],
            ),
        ],
    )
)

register_type(
    TypeConfig(
        name="preprocess_batch",
        label="Preprocess Batch",
        plural_label="Preprocess Batches",
        category="temporal",
        navigable=False,
        render_mode="list",
        default_sort="created_at",
        search_fields=["original_filename"],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("original_filename", "Filename", required=True),
            PropertyDef(
                "status",
                "Status",
                data_type="enum",
                enum_values=["preprocessing", "identified", "confirmed", "failed"],
            ),
            PropertyDef("page_count", "Page Count", data_type="number"),
            PropertyDef(
                "sections_identified", "Sections Identified", data_type="number"
            ),
            PropertyDef("sections_matched", "Sections Matched", data_type="number"),
        ],
    )
)

register_type(
    TypeConfig(
        name="extraction_batch",
        label="Extraction Batch",
        plural_label="Extraction Batches",
        category="temporal",
        navigable=False,
        render_mode="list",
        default_sort="created_at",
        search_fields=[],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef(
                "status",
                "Status",
                data_type="enum",
                required=True,
                enum_values=[
                    "pending",
                    "extracting",
                    "extracted",
                    "confirmed",
                    "failed",
                ],
            ),
            PropertyDef("specification_item_id", "Specification", data_type="string"),
            PropertyDef("preprocess_batch_id", "Preprocess Batch", data_type="string"),
            PropertyDef("context_id", "Context Milestone", data_type="string"),
            PropertyDef("sections_total", "Total Sections", data_type="number"),
            PropertyDef("sections_extracted", "Sections Extracted", data_type="number"),
            PropertyDef("sections_failed", "Sections Failed", data_type="number"),
        ],
    )
)


# ─── Workflow Types ────────────────────────────────────────────

register_type(
    TypeConfig(
        name="change",
        label="Change",
        plural_label="Changes",
        category="workflow",
        # Workflow items point TO what they reference
        valid_targets=["door", "room", "floor", "building"],
        navigable=True,
        render_mode="table",
        default_sort="created_at",
        search_fields=["property_name"],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("property_name", "Property", required=True),
            PropertyDef("previous_value", "Previous Value"),
            PropertyDef("new_value", "New Value"),
            PropertyDef(
                "status",
                "Status",
                data_type="enum",
                enum_values=["detected", "acknowledged", "reviewed"],
            ),
        ],
    )
)

register_type(
    TypeConfig(
        name="conflict",
        label="Conflict",
        plural_label="Conflicts",
        category="workflow",
        valid_targets=["door", "room", "floor", "building"],
        navigable=True,
        render_mode="table",
        default_sort="created_at",
        search_fields=["property_name"],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("property_name", "Property", required=True),
            PropertyDef(
                "status",
                "Status",
                data_type="enum",
                enum_values=["detected", "acknowledged", "resolved"],
                required=True,
            ),
        ],
    )
)

register_type(
    TypeConfig(
        name="decision",
        label="Decision",
        plural_label="Decisions",
        category="workflow",
        is_source_type=True,  # Decisions act as resolution sources
        valid_targets=["conflict"],
        navigable=True,
        render_mode="list",
        default_sort="created_at",
        search_fields=["rationale", "decided_by"],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("rationale", "Rationale"),
            PropertyDef("resolved_value", "Resolved Value"),
            PropertyDef("decided_by", "Decided By"),
        ],
    )
)

register_type(
    TypeConfig(
        name="directive",
        label="Directive",
        plural_label="Directives",
        category="workflow",
        valid_targets=["door", "room", "floor", "building"],
        navigable=True,
        render_mode="table",
        default_sort="created_at",
        search_fields=["property_name", "status"],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("property_name", "Property", required=True),
            PropertyDef("target_value", "Target Value"),
            PropertyDef("target_source_id", "Target Source", required=True),
            PropertyDef("decision_item_id", "Decision"),
            PropertyDef("affected_item_id", "Affected Item"),
            PropertyDef(
                "status",
                "Status",
                data_type="enum",
                enum_values=["pending", "fulfilled", "superseded"],
                required=True,
            ),
        ],
    )
)

register_type(
    TypeConfig(
        name="note",
        label="Note",
        plural_label="Notes",
        category="workflow",
        valid_targets=[
            "door",
            "room",
            "floor",
            "building",
            "conflict",
            "change",
            "decision",
        ],
        navigable=False,
        render_mode="list",
        default_sort="created_at",
        search_fields=["content"],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("content", "Content", required=True),
        ],
    )
)


# ─── Definition types ──────────────────────────────────────────

register_type(
    TypeConfig(
        name="property",
        label="Property",
        plural_label="Properties",
        category="definition",
        icon="tag",
        navigable=True,
        render_mode="list",
        default_sort="identifier",
        search_fields=["property_name", "label"],
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("property_name", "Property Name", required=True),
            PropertyDef("parent_type", "Parent Type", required=True),
            PropertyDef("label", "Display Label", required=True),
            PropertyDef("data_type", "Data Type"),
            PropertyDef("unit", "Unit"),
        ],
    )
)


register_type(
    TypeConfig(
        name="type_definition",
        label="Type Definition",
        plural_label="Type Definitions",
        category="definition",
        navigable=False,
        exclude_from_conflicts=True,
        properties=[
            PropertyDef("type_name", "Type Name", required=True),
            PropertyDef("label", "Label", required=True),
            PropertyDef("plural_label", "Plural Label"),
            PropertyDef("category", "Category"),
            PropertyDef("render_mode", "Render Mode"),
            PropertyDef("property_defs", "Property Definitions"),
        ],
    )
)
