"""
Item type configuration.

Types are application configuration, not database schema.
Adding a new type requires zero migrations — just an entry here.

Each type defines:
  - display metadata (label, icon, color)
  - which properties are expected
  - which connection targets are valid
  - navigation behavior
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
    is_context_type: bool = False


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


# ─── Organization Types ────────────────────────────────────────

register_type(TypeConfig(
    name="project",
    label="Project",
    plural_label="Projects",
    category="organization",
    valid_targets=["building", "schedule", "specification", "milestone", "phase"],
    navigable=True,
))

register_type(TypeConfig(
    name="portfolio",
    label="Portfolio",
    plural_label="Portfolios",
    category="organization",
    valid_targets=["project"],
    navigable=True,
))

register_type(TypeConfig(
    name="firm",
    label="Firm",
    plural_label="Firms",
    category="organization",
    valid_targets=["portfolio", "project"],
    navigable=True,
))


# ─── Spatial Types ─────────────────────────────────────────────

register_type(TypeConfig(
    name="building",
    label="Building",
    plural_label="Buildings",
    category="spatial",
    valid_targets=["floor"],
    navigable=True,
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
    navigable=False,
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
    navigable=False,
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
    properties=[
        PropertyDef("content", "Content", required=True),
    ],
))
