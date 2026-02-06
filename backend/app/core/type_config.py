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
    """Definition of an expected property on an item type."""
    name: str
    label: str
    data_type: str = "string"  # string, number, boolean, date, enum
    required: bool = False
    enum_values: list[str] | None = None
    unit: str | None = None
    description: str = ""


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


# ─── Organization Types ────────────────────────────────────────

register_type(TypeConfig(
    name="project",
    label="Project",
    plural_label="Projects",
    category="organization",
    valid_targets=["building", "schedule", "specification", "milestone", "phase"],
    navigable=True,
    render_mode="cards",
    default_sort="name",
    search_fields=["name"],
))

register_type(TypeConfig(
    name="portfolio",
    label="Portfolio",
    plural_label="Portfolios",
    category="organization",
    valid_targets=["project"],
    navigable=True,
    render_mode="cards",
    default_sort="name",
    search_fields=["name"],
))

register_type(TypeConfig(
    name="firm",
    label="Firm",
    plural_label="Firms",
    category="organization",
    valid_targets=["portfolio", "project"],
    navigable=True,
    render_mode="cards",
    default_sort="name",
    search_fields=["name"],
))


# ─── Spatial Types ─────────────────────────────────────────────

register_type(TypeConfig(
    name="building",
    label="Building",
    plural_label="Buildings",
    category="spatial",
    valid_targets=["floor"],
    navigable=True,
    render_mode="list",
    default_sort="name",
    search_fields=["name", "address"],
    properties=[
        PropertyDef("name", "Name", required=True),
        PropertyDef("address", "Address"),
    ],
))

register_type(TypeConfig(
    name="floor",
    label="Floor",
    plural_label="Floors",
    category="spatial",
    valid_targets=["room"],
    navigable=True,
    render_mode="list",
    default_sort="level",
    search_fields=["name"],
    properties=[
        PropertyDef("name", "Name", required=True),
        PropertyDef("level", "Level", data_type="number"),
    ],
))

register_type(TypeConfig(
    name="room",
    label="Room",
    plural_label="Rooms",
    category="spatial",
    valid_targets=["door"],
    navigable=True,
    render_mode="cards",
    default_sort="number",
    search_fields=["name", "number"],
    properties=[
        PropertyDef("name", "Name", required=True),
        PropertyDef("number", "Room Number"),
        PropertyDef("area", "Area", data_type="number", unit="sf"),
        PropertyDef("finish_floor", "Floor Finish"),
        PropertyDef("finish_wall", "Wall Finish"),
        PropertyDef("finish_ceiling", "Ceiling Finish"),
    ],
))

register_type(TypeConfig(
    name="door",
    label="Door",
    plural_label="Doors",
    category="spatial",
    valid_targets=[],
    navigable=True,
    render_mode="table",
    default_sort="mark",
    search_fields=["mark", "type", "hardware_set"],
    properties=[
        PropertyDef("mark", "Mark", required=True),
        PropertyDef("width", "Width", data_type="number", unit="in"),
        PropertyDef("height", "Height", data_type="number", unit="in"),
        PropertyDef("type", "Door Type"),
        PropertyDef("hardware_set", "Hardware Set"),
        PropertyDef("fire_rating", "Fire Rating"),
        PropertyDef("frame_type", "Frame Type"),
        PropertyDef("glazing", "Glazing"),
    ],
))


# ─── Document Types ────────────────────────────────────────────

register_type(TypeConfig(
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
))

register_type(TypeConfig(
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
))

register_type(TypeConfig(
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
))


# ─── Temporal Types ────────────────────────────────────────────

register_type(TypeConfig(
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
        PropertyDef("ordinal", "Ordinal", data_type="number", required=True,
                     description="Determines sequence: 100, 200, 300..."),
        PropertyDef("date", "Date", data_type="date"),
        PropertyDef("phase", "Phase"),
    ],
))

register_type(TypeConfig(
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
))

register_type(TypeConfig(
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
        PropertyDef("status", "Status", data_type="enum",
                     enum_values=["pending", "processing", "completed", "failed"]),
    ],
))


# ─── Workflow Types ────────────────────────────────────────────

register_type(TypeConfig(
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
        PropertyDef("status", "Status", data_type="enum",
                     enum_values=["detected", "acknowledged", "reviewed"]),
    ],
))

register_type(TypeConfig(
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
        PropertyDef("status", "Status", data_type="enum",
                     enum_values=["detected", "acknowledged", "resolved"],
                     required=True),
    ],
))

register_type(TypeConfig(
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
))

register_type(TypeConfig(
    name="note",
    label="Note",
    plural_label="Notes",
    category="workflow",
    valid_targets=["door", "room", "floor", "building", "conflict", "change", "decision"],
    navigable=False,
    render_mode="list",
    default_sort="created_at",
    search_fields=["content"],
    exclude_from_conflicts=True,
    properties=[
        PropertyDef("content", "Content", required=True),
    ],
))
