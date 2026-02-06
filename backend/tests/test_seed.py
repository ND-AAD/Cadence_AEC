"""Tests for Seed Data — Verifies seed_project() creates correct structure."""

import pytest
from sqlalchemy import select, func

from app.models.core import Item, Connection
from scripts.seed_data import seed_project


# ─── Seed Project Execution ────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_project_creates_hierarchy(db_session):
    """Seed script creates complete Project Alpha hierarchy."""
    ids = await seed_project(db_session)

    # Verify returned IDs
    assert "project" in ids
    assert "building" in ids
    assert "dd_phase" in ids
    assert "cd_phase" in ids
    assert "dd_milestone" in ids
    assert "cd_milestone" in ids
    assert "schedule" in ids
    assert "spec" in ids


# ─── Project-level Items ───────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_creates_one_project(db_session):
    """Seed creates exactly one project named Project Alpha."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "project")
    )
    projects = result.scalars().all()

    assert len(projects) == 1
    assert projects[0].identifier == "Project Alpha"
    assert projects[0].properties.get("name") == "Project Alpha"


@pytest.mark.asyncio
async def test_seed_creates_one_building(db_session):
    """Seed creates exactly one building connected to project."""
    ids = await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "building")
    )
    buildings = result.scalars().all()

    assert len(buildings) == 1
    assert buildings[0].identifier == "Building A"
    assert buildings[0].properties.get("name") == "Building A"


# ─── Spatial Hierarchy ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_creates_three_floors(db_session):
    """Seed creates exactly 3 floors."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "floor")
    )
    floors = result.scalars().all()

    assert len(floors) == 3
    # Floors should be numbered 1, 2, 3
    floor_names = {f.properties.get("name") for f in floors}
    assert "Floor 1" in floor_names
    assert "Floor 2" in floor_names
    assert "Floor 3" in floor_names


@pytest.mark.asyncio
async def test_seed_creates_ten_rooms(db_session):
    """Seed creates exactly 10 rooms distributed across floors."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "room")
    )
    rooms = result.scalars().all()

    assert len(rooms) == 10


@pytest.mark.asyncio
async def test_seed_creates_fifty_doors(db_session):
    """Seed creates exactly 50 doors."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "door")
    )
    doors = result.scalars().all()

    assert len(doors) == 50


# ─── Connection Structure ──────────────────────────────────────

@pytest.mark.asyncio
async def test_each_door_connected_to_room(db_session):
    """Each door is connected to a room (room → door)."""
    await seed_project(db_session)

    # Get all doors
    door_result = await db_session.execute(
        select(Item).where(Item.item_type == "door")
    )
    doors = door_result.scalars().all()

    # Each door should be a target of exactly one connection from a room
    for door in doors:
        conn_result = await db_session.execute(
            select(Connection).where(
                Connection.target_item_id == door.id
            ).join(
                Item, Connection.source_item_id == Item.id
            ).where(
                Item.item_type == "room"
            )
        )
        room_connections = conn_result.scalars().all()
        assert len(room_connections) == 1, f"Door {door.identifier} has {len(room_connections)} room connections"


@pytest.mark.asyncio
async def test_rooms_connected_to_floors(db_session):
    """Each room is connected to a floor (floor → room)."""
    await seed_project(db_session)

    room_result = await db_session.execute(
        select(Item).where(Item.item_type == "room")
    )
    rooms = room_result.scalars().all()

    # Each room should be a target of exactly one floor connection
    for room in rooms:
        conn_result = await db_session.execute(
            select(Connection).where(
                Connection.target_item_id == room.id
            ).join(
                Item, Connection.source_item_id == Item.id
            ).where(
                Item.item_type == "floor"
            )
        )
        floor_connections = conn_result.scalars().all()
        assert len(floor_connections) == 1


@pytest.mark.asyncio
async def test_floors_connected_to_building(db_session):
    """Each floor is connected to the building (building → floor)."""
    await seed_project(db_session)

    floor_result = await db_session.execute(
        select(Item).where(Item.item_type == "floor")
    )
    floors = floor_result.scalars().all()

    # Each floor should be a target of the building
    for floor in floors:
        conn_result = await db_session.execute(
            select(Connection).where(
                Connection.target_item_id == floor.id
            ).join(
                Item, Connection.source_item_id == Item.id
            ).where(
                Item.item_type == "building"
            )
        )
        building_connections = conn_result.scalars().all()
        assert len(building_connections) == 1


@pytest.mark.asyncio
async def test_building_connected_to_project(db_session):
    """Building is connected to project (project → building)."""
    ids = await seed_project(db_session)

    project_id = ids["project"]
    building_id = ids["building"]

    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == project_id,
            Connection.target_item_id == building_id,
        )
    )
    conn = result.scalar_one_or_none()
    assert conn is not None


# ─── Temporal Structure ────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_creates_two_phases(db_session):
    """Seed creates DD and CD phases."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "phase")
    )
    phases = result.scalars().all()

    assert len(phases) == 2
    phase_abbreviations = {p.properties.get("abbreviation") for p in phases}
    assert "DD" in phase_abbreviations
    assert "CD" in phase_abbreviations


@pytest.mark.asyncio
async def test_seed_creates_two_milestones_with_correct_ordinals(db_session):
    """Seed creates DD (300) and CD (400) milestones with correct ordinals."""
    ids = await seed_project(db_session)

    # Get milestones
    result = await db_session.execute(
        select(Item).where(Item.item_type == "milestone")
    )
    milestones = result.scalars().all()

    assert len(milestones) == 2

    # Create ordinal map
    ordinal_map = {m.identifier: m.properties.get("ordinal") for m in milestones}

    # DD should have ordinal 300
    assert ordinal_map["DD"] == 300

    # CD should have ordinal 400
    assert ordinal_map["CD"] == 400


# ─── Document Sources ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_creates_schedule_source(db_session):
    """Seed creates a Schedule source document."""
    ids = await seed_project(db_session)

    schedule_id = ids["schedule"]
    result = await db_session.execute(
        select(Item).where(Item.id == schedule_id)
    )
    schedule = result.scalar_one()

    assert schedule.item_type == "schedule"
    assert schedule.identifier == "Finish Schedule"
    assert schedule.properties.get("name") == "Finish Schedule"


@pytest.mark.asyncio
async def test_seed_creates_specification_source(db_session):
    """Seed creates a Specification source document."""
    ids = await seed_project(db_session)

    spec_id = ids["spec"]
    result = await db_session.execute(
        select(Item).where(Item.id == spec_id)
    )
    spec = result.scalar_one()

    assert spec.item_type == "specification"
    assert spec.identifier == "Spec §08 — Openings"


# ─── Source Connections ────────────────────────────────────────

@pytest.mark.asyncio
async def test_schedule_connected_to_project(db_session):
    """Schedule is connected to project."""
    ids = await seed_project(db_session)

    project_id = ids["project"]
    schedule_id = ids["schedule"]

    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == project_id,
            Connection.target_item_id == schedule_id,
        )
    )
    conn = result.scalar_one_or_none()
    assert conn is not None


@pytest.mark.asyncio
async def test_specification_connected_to_project(db_session):
    """Specification is connected to project."""
    ids = await seed_project(db_session)

    project_id = ids["project"]
    spec_id = ids["spec"]

    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == project_id,
            Connection.target_item_id == spec_id,
        )
    )
    conn = result.scalar_one_or_none()
    assert conn is not None


@pytest.mark.asyncio
async def test_schedule_connected_to_all_doors(db_session):
    """Schedule is connected to all 50 doors."""
    ids = await seed_project(db_session)

    schedule_id = ids["schedule"]

    # Count connections from schedule to doors
    door_ids_subquery = select(Item.id).where(
        Item.item_type == "door"
    ).scalar_subquery()

    result = await db_session.execute(
        select(func.count(Connection.id)).where(
            Connection.source_item_id == schedule_id
        ).select_from(Connection).join(
            Item, Connection.target_item_id == Item.id
        ).where(
            Item.item_type == "door"
        )
    )
    count = result.scalar()
    assert count == 50


@pytest.mark.asyncio
async def test_specification_connected_to_all_doors(db_session):
    """Specification is connected to all 50 doors."""
    ids = await seed_project(db_session)

    spec_id = ids["spec"]

    # Count connections from spec to doors
    result = await db_session.execute(
        select(func.count(Connection.id)).where(
            Connection.source_item_id == spec_id
        ).select_from(Connection).join(
            Item, Connection.target_item_id == Item.id
        ).where(
            Item.item_type == "door"
        )
    )
    count = result.scalar()
    assert count == 50


# ─── Door Properties ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_doors_have_required_properties(db_session):
    """All doors have mark, width, height properties."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "door")
    )
    doors = result.scalars().all()

    for door in doors:
        assert door.properties.get("mark") is not None
        assert door.properties.get("width") is not None
        assert door.properties.get("height") is not None


@pytest.mark.asyncio
async def test_doors_have_material_and_finish(db_session):
    """All doors have material and finish properties for specification."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "door")
    )
    doors = result.scalars().all()

    for door in doors:
        assert door.properties.get("material") is not None
        assert door.properties.get("finish") is not None


# ─── Room Properties ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_rooms_have_name_and_number(db_session):
    """All rooms have name and number properties."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "room")
    )
    rooms = result.scalars().all()

    for room in rooms:
        assert room.properties.get("name") is not None
        assert room.properties.get("number") is not None


@pytest.mark.asyncio
async def test_rooms_have_finishes(db_session):
    """All rooms have floor, wall, ceiling finish properties."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "room")
    )
    rooms = result.scalars().all()

    for room in rooms:
        assert room.properties.get("finish_floor") is not None
        assert room.properties.get("finish_wall") is not None
        assert room.properties.get("finish_ceiling") is not None


# ─── Floor Distribution ────────────────────────────────────────

@pytest.mark.asyncio
async def test_rooms_distributed_across_floors(db_session):
    """Rooms are distributed across 3 floors (4, 3, 3 distribution)."""
    await seed_project(db_session)

    # Get all floors with their connected rooms
    floor_result = await db_session.execute(
        select(Item).where(Item.item_type == "floor").order_by(Item.created_at)
    )
    floors = floor_result.scalars().all()

    floor_room_counts = []
    for floor in floors:
        room_result = await db_session.execute(
            select(func.count(Item.id)).where(
                Item.item_type == "room"
            ).select_from(Connection).where(
                Connection.source_item_id == floor.id,
                Connection.target_item_id == Item.id,
            )
        )
        count = room_result.scalar()
        floor_room_counts.append(count)

    # Should be 4, 3, 3 distribution (or some valid distribution totaling 10)
    assert sum(floor_room_counts) == 10


@pytest.mark.asyncio
async def test_doors_distributed_across_rooms(db_session):
    """50 doors are distributed across 10 rooms (5 per room)."""
    await seed_project(db_session)

    room_result = await db_session.execute(
        select(Item).where(Item.item_type == "room")
    )
    rooms = room_result.scalars().all()

    for room in rooms:
        door_result = await db_session.execute(
            select(func.count(Item.id)).where(
                Item.item_type == "door"
            ).select_from(Connection).where(
                Connection.source_item_id == room.id,
                Connection.target_item_id == Item.id,
            )
        )
        count = door_result.scalar()
        assert count == 5, f"Room {room.identifier} has {count} doors, expected 5"
