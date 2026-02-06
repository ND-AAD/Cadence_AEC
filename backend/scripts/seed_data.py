"""
Seed data script — creates a realistic Project Alpha.

Per WP-3 acceptance criteria:
  - 1 Project ("Project Alpha")
  - 1 Building ("Building A")
  - 3 Floors
  - 10 Rooms (distributed across floors)
  - 50 Doors (distributed across rooms)
  - 2 Phases (DD, CD) with milestones
  - 1 Schedule source ("Finish Schedule")
  - 1 Specification source ("Spec §08 — Openings")
  - All connections wired up

Usage:
  python -m scripts.seed_data

  Or via API calls (this script uses httpx to call the running API).
  Alternatively, import and call seed_project() with a database session.
"""

import asyncio
import random
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Ensure models are imported so Base.metadata is populated
from app.models.core import Item, Connection  # noqa: F401
from app.models.infrastructure import User  # noqa: F401
from app.core.config import settings


# ─── Door property generators ──────────────────────────────────

FINISHES = ["Paint", "Stain", "Laminate", "Veneer", "Powder Coat"]
MATERIALS = ["Wood", "Hollow Metal", "Aluminum", "FRP", "Steel"]
HARDWARE_SETS = ["HS-1", "HS-2", "HS-3", "HS-4", "HS-5", "HS-6"]
FRAME_TYPES = ["Hollow Metal", "Wood", "Aluminum", "Steel Welded"]
FIRE_RATINGS = ["", "20 min", "45 min", "60 min", "90 min"]
GLAZING_OPTIONS = ["None", "1/4 Clear Tempered", "Wire Glass", "Frosted"]
DOOR_TYPES = ["A", "B", "C", "D", "E", "F", "G"]

DOOR_WIDTHS = [30, 32, 34, 36, 42, 48]  # inches
DOOR_HEIGHTS = [80, 84, 96]  # inches

ROOM_FINISHES_FLOOR = ["VCT", "Carpet", "Ceramic Tile", "Polished Concrete", "Rubber"]
ROOM_FINISHES_WALL = ["Paint", "FRP", "Ceramic Tile", "Vinyl Wallcovering"]
ROOM_FINISHES_CEILING = ["ACT 2x4", "ACT 2x2", "GWB", "Exposed Structure"]

ROOM_TYPES = [
    ("Office", range(100, 200)),
    ("Conference Room", range(200, 210)),
    ("Storage", range(300, 310)),
    ("Restroom", range(400, 410)),
    ("Corridor", range(500, 510)),
    ("Mechanical", range(600, 610)),
    ("Break Room", range(700, 710)),
    ("Lobby", range(800, 810)),
]


def make_door_properties(idx: int) -> dict:
    """Generate realistic door properties."""
    random.seed(idx)  # Reproducible
    return {
        "mark": f"D{101 + idx:03d}",
        "width": random.choice(DOOR_WIDTHS),
        "height": random.choice(DOOR_HEIGHTS),
        "type": random.choice(DOOR_TYPES),
        "hardware_set": random.choice(HARDWARE_SETS),
        "fire_rating": random.choice(FIRE_RATINGS),
        "frame_type": random.choice(FRAME_TYPES),
        "finish": random.choice(FINISHES),
        "material": random.choice(MATERIALS),
        "glazing": random.choice(GLAZING_OPTIONS),
    }


def make_room_properties(floor_num: int, room_idx: int) -> dict:
    """Generate realistic room properties."""
    random.seed(floor_num * 100 + room_idx)
    room_type, _ = random.choice(ROOM_TYPES)
    number = f"{floor_num}{room_idx + 1:02d}"
    return {
        "name": f"{room_type} {number}",
        "number": number,
        "area": random.randint(80, 500),
        "finish_floor": random.choice(ROOM_FINISHES_FLOOR),
        "finish_wall": random.choice(ROOM_FINISHES_WALL),
        "finish_ceiling": random.choice(ROOM_FINISHES_CEILING),
    }


# ─── Seed function ─────────────────────────────────────────────

async def seed_project(db: AsyncSession) -> dict[str, uuid.UUID]:
    """
    Create the complete Project Alpha hierarchy.
    Returns a dict of key item names → UUIDs for reference.
    """
    ids: dict[str, uuid.UUID] = {}

    def make_item(item_type: str, identifier: str, properties: dict | None = None) -> Item:
        item = Item(
            item_type=item_type,
            identifier=identifier,
            properties=properties or {},
        )
        db.add(item)
        return item

    def connect(source: Item, target: Item, props: dict | None = None) -> Connection:
        conn = Connection(
            source_item_id=source.id,
            target_item_id=target.id,
            properties=props or {},
        )
        db.add(conn)
        return conn

    # ── Test user ──────────────────────────────────────────
    user = User(email="nick@cadence.dev", name="Nick")
    db.add(user)
    await db.flush()
    ids["user"] = user.id

    # ── Project ────────────────────────────────────────────
    project = make_item("project", "Project Alpha", {
        "name": "Project Alpha",
        "description": "Mixed-use renovation — 3 floors, 50 doors",
    })
    await db.flush()
    ids["project"] = project.id

    # ── Phases & Milestones ────────────────────────────────
    dd_phase = make_item("phase", "Design Development", {
        "name": "Design Development",
        "abbreviation": "DD",
    })
    cd_phase = make_item("phase", "Construction Documents", {
        "name": "Construction Documents",
        "abbreviation": "CD",
    })
    await db.flush()

    dd_milestone = make_item("milestone", "DD", {
        "name": "Design Development",
        "ordinal": 300,
        "phase": "DD",
    })
    cd_milestone = make_item("milestone", "CD", {
        "name": "Construction Documents",
        "ordinal": 400,
        "phase": "CD",
    })
    await db.flush()
    ids["dd_phase"] = dd_phase.id
    ids["cd_phase"] = cd_phase.id
    ids["dd_milestone"] = dd_milestone.id
    ids["cd_milestone"] = cd_milestone.id

    # Phase connections
    connect(project, dd_phase)
    connect(project, cd_phase)
    connect(dd_phase, dd_milestone)
    connect(cd_phase, cd_milestone)

    # ── Sources ────────────────────────────────────────────
    schedule = make_item("schedule", "Finish Schedule", {
        "name": "Finish Schedule",
        "document_number": "A-601",
        "discipline": "Architecture",
    })
    spec = make_item("specification", "Spec §08 — Openings", {
        "name": "Specification Section 08 — Openings",
        "section_number": "08 00 00",
        "discipline": "Architecture",
    })
    await db.flush()
    ids["schedule"] = schedule.id
    ids["spec"] = spec.id

    connect(project, schedule)
    connect(project, spec)

    # ── Building ───────────────────────────────────────────
    building = make_item("building", "Building A", {
        "name": "Building A",
        "address": "100 Main Street",
    })
    await db.flush()
    ids["building"] = building.id
    connect(project, building)

    # ── Floors ─────────────────────────────────────────────
    floors = []
    for f in range(1, 4):
        floor = make_item("floor", f"Floor {f}", {
            "name": f"Floor {f}",
            "level": f,
        })
        floors.append(floor)
    await db.flush()
    for f_idx, floor in enumerate(floors):
        ids[f"floor_{f_idx + 1}"] = floor.id
        connect(building, floor)

    # ── Rooms ──────────────────────────────────────────────
    # Distribute: Floor 1 gets 4 rooms, Floor 2 gets 3, Floor 3 gets 3
    room_distribution = [4, 3, 3]
    rooms = []
    for f_idx, floor in enumerate(floors):
        floor_num = f_idx + 1
        for r_idx in range(room_distribution[f_idx]):
            props = make_room_properties(floor_num, r_idx)
            room = make_item("room", props["number"], props)
            rooms.append((room, floor))
    await db.flush()
    for r_idx, (room, floor) in enumerate(rooms):
        ids[f"room_{room.identifier}"] = room.id
        connect(floor, room)

    # ── Doors ──────────────────────────────────────────────
    # Distribute 50 doors across 10 rooms (5 per room)
    doors = []
    door_idx = 0
    for room, floor in rooms:
        doors_per_room = 5
        for d in range(doors_per_room):
            props = make_door_properties(door_idx)
            door = make_item("door", props["mark"], props)
            doors.append((door, room))
            door_idx += 1
    await db.flush()

    for door, room in doors:
        ids[f"door_{door.identifier}"] = door.id
        connect(room, door)
        # Sources connect to doors (schedule → door, spec → door)
        connect(schedule, door)
        connect(spec, door)

    await db.flush()

    print(f"Seeded Project Alpha:")
    print(f"  Project:     {ids['project']}")
    print(f"  Building:    1")
    print(f"  Floors:      {len(floors)}")
    print(f"  Rooms:       {len(rooms)}")
    print(f"  Doors:       {len(doors)}")
    print(f"  Milestones:  DD ({ids['dd_milestone']}), CD ({ids['cd_milestone']})")
    print(f"  Sources:     Schedule ({ids['schedule']}), Spec ({ids['spec']})")
    print(f"  Connections: ~{len(doors) * 3 + len(rooms) + len(floors) + 6}")

    return ids


# ─── CLI entry point ───────────────────────────────────────────

async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            ids = await seed_project(session)

    await engine.dispose()
    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(main())
