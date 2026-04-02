"""
Starter catalog for firm vocabulary seeding (WP-DYN).

These spatial types are pre-seeded when a new account is created.
They are firm vocabulary, not OS types -- editable, deletable, not special.
"""

from app.core.type_config import TypeConfig, PropertyDef

STARTER_TYPES: list[TypeConfig] = [
    TypeConfig(
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
    ),
    TypeConfig(
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
    ),
    TypeConfig(
        name="room",
        label="Room",
        plural_label="Rooms",
        category="spatial",
        valid_targets=["door"],
        navigable=True,
        render_mode="cards",
        default_sort="number",
        search_fields=["name", "number"],
        masterformat_divisions=("09",),
        properties=[
            PropertyDef(
                "name", "Name", required=True, aliases=("room_name", "rm_name")
            ),
            PropertyDef(
                "number", "Room Number", aliases=("room_number", "rm_no", "rm_#")
            ),
            PropertyDef(
                "area",
                "Area",
                data_type="number",
                unit="sf",
                aliases=("sf", "sqft", "sq_ft", "area_sf"),
            ),
            PropertyDef(
                "finish_floor", "Floor Finish", aliases=("floor_finish", "flr_finish")
            ),
            PropertyDef(
                "finish_wall", "Wall Finish", aliases=("wall_finish", "wl_finish")
            ),
            PropertyDef(
                "finish_ceiling",
                "Ceiling Finish",
                aliases=("ceiling_finish", "clg_finish"),
            ),
            PropertyDef(
                "ceiling_height",
                "Ceiling Height",
                data_type="number",
                unit="in",
                normalization="dimension",
                aliases=("clg_height", "ceiling_ht"),
            ),
        ],
    ),
    TypeConfig(
        name="frame",
        label="Frame",
        plural_label="Frames",
        category="spatial",
        valid_targets=[],
        navigable=True,
        render_mode="list",
        default_sort="identifier",
        search_fields=["material", "type"],
        masterformat_divisions=("08",),
        properties=[
            PropertyDef(
                "material",
                "Material",
                description="Frame material (e.g., hollow metal, aluminum)",
            ),
            PropertyDef("gauge", "Gauge", description="Metal gauge (e.g., 16 gauge)"),
            PropertyDef("finish", "Finish", description="Applied finish or coating"),
            PropertyDef(
                "fire_rating", "Fire Rating", description="UL fire rating label"
            ),
            PropertyDef(
                "type",
                "Frame Type",
                description="Frame profile type (e.g., knocked-down, welded)",
            ),
        ],
    ),
    TypeConfig(
        name="door",
        label="Door",
        plural_label="Doors",
        category="spatial",
        valid_targets=[],
        navigable=True,
        render_mode="table",
        default_sort="mark",
        search_fields=["mark", "type", "hardware_set"],
        masterformat_divisions=("08",),
        properties=[
            PropertyDef(
                "mark",
                "Mark",
                required=True,
                aliases=("number", "door_mark", "door_number", "door_no"),
            ),
            PropertyDef("level", "Level", aliases=("floor", "story", "flr")),
            PropertyDef(
                "width",
                "Width",
                data_type="number",
                unit="in",
                normalization="dimension",
                aliases=("w", "door_width", "clear_width"),
            ),
            PropertyDef(
                "height",
                "Height",
                data_type="number",
                unit="in",
                normalization="dimension",
                aliases=("h", "door_height", "clear_height"),
            ),
            PropertyDef(
                "thickness",
                "Thickness",
                data_type="number",
                unit="in",
                normalization="dimension",
                aliases=("t", "door_thickness", "thk"),
            ),
            PropertyDef("type", "Door Type", aliases=("door_type", "dt", "style")),
            PropertyDef(
                "material", "Material", aliases=("door_material", "mat", "mtl")
            ),
            PropertyDef(
                "finish", "Finish", aliases=("fnsh", "door_finish", "surface_finish")
            ),
            PropertyDef(
                "hardware_set",
                "Hardware Set",
                aliases=("hw", "hw_set", "hardware", "hardware_group", "hdw"),
            ),
            PropertyDef(
                "fire_rating",
                "Fire Rating",
                aliases=("fr", "fire_rate", "rating", "f.r.", "fire_rated"),
            ),
            PropertyDef("frame_type", "Frame Type", aliases=("frame",)),
            PropertyDef("frame_material", "Frame Material"),
            PropertyDef("frame_finish", "Frame Finish"),
            PropertyDef(
                "glazing",
                "Glazing",
                aliases=("glass", "gl", "glass_type", "lite", "vision_panel"),
            ),
            PropertyDef("location", "Location", aliases=("room", "room_name", "rm")),
            PropertyDef("location_to", "Location To", aliases=("to",)),
            PropertyDef("handing", "Handing", aliases=("hand",)),
            PropertyDef("swing", "Swing"),
            PropertyDef("closer", "Closer", aliases=("door_closer", "cl")),
            PropertyDef(
                "lock_function",
                "Lock Function",
                aliases=("lock", "lockset", "lock_type"),
            ),
            PropertyDef(
                "rebate_width",
                "Rebate Width",
                data_type="number",
                unit="in",
                normalization="dimension",
                aliases=("rabbet_width", "rebate_w"),
            ),
            PropertyDef(
                "rebate_height",
                "Rebate Height",
                data_type="number",
                unit="in",
                normalization="dimension",
                aliases=("rabbet_height", "rebate_h"),
            ),
            PropertyDef("panel_type", "Panel Type", aliases=("panel",)),
        ],
    ),
    TypeConfig(
        name="window",
        label="Window",
        plural_label="Windows",
        category="spatial",
        render_mode="table",
        default_sort="mark",
        search_fields=["mark", "type", "material"],
        masterformat_divisions=("08",),
        valid_targets=[],
        properties=[
            PropertyDef(
                "mark",
                "Mark",
                required=True,
                aliases=("number", "window_mark", "window_number", "win_mark"),
            ),
            PropertyDef(
                "width",
                "Width",
                data_type="number",
                unit="in",
                normalization="dimension",
                aliases=("w", "window_width"),
            ),
            PropertyDef(
                "height",
                "Height",
                data_type="number",
                unit="in",
                normalization="dimension",
                aliases=("h", "window_height"),
            ),
            PropertyDef("type", "Type", aliases=("window_type", "wt", "style")),
            PropertyDef(
                "material", "Material", aliases=("window_material", "mat", "mtl")
            ),
            PropertyDef("finish", "Finish", aliases=("window_finish", "fnsh")),
            PropertyDef(
                "glazing", "Glazing", aliases=("glass", "gl", "glass_type")
            ),
            PropertyDef("frame_material", "Frame Material", aliases=("frame_mat",)),
            PropertyDef("frame_finish", "Frame Finish"),
            PropertyDef(
                "fire_rating", "Fire Rating", aliases=("fr", "fire_rate", "rating")
            ),
            PropertyDef("hardware", "Hardware", aliases=("hw", "hardware_set")),
            PropertyDef(
                "operation", "Operation", aliases=("op", "operation_type")
            ),
            PropertyDef(
                "sill_height",
                "Sill Height",
                data_type="number",
                unit="in",
                normalization="dimension",
                aliases=("sill_ht", "sill"),
            ),
        ],
    ),
]
