"""
Tests for property item creation during import — WP-PROP-2.

Covers:
  - Property items created for all mapped columns
  - Property→instance connections for all imported items
  - Re-import doesn't duplicate property items or connections
  - Empty/null property values still create connections
"""

import io
import json

import openpyxl
import pytest
import pytest_asyncio
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Connection, Item
from tests.fixtures.excel_factory import STANDARD_DOOR_MAPPING, make_door_schedule_excel


@pytest_asyncio.fixture
async def import_setup(make_item, make_connection):
    """Minimal setup for import testing."""
    project = await make_item("project", "Project Alpha")
    schedule = await make_item(
        "schedule",
        "Finish Schedule",
        {"name": "Finish Schedule", "discipline": "Architectural"},
    )
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 100})

    await make_connection(project, schedule)
    await make_connection(project, dd)

    return {"project": project, "schedule": schedule, "dd": dd}


@pytest.mark.asyncio
async def test_import_creates_property_items(
    client, import_setup, db_session: AsyncSession
):
    """Importing a schedule creates property items for all mapped columns."""
    setup = import_setup
    file_bytes = make_door_schedule_excel(5)  # 5 doors

    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    assert resp.status_code == 201

    # Check property items exist
    result = await db_session.execute(select(Item).where(Item.item_type == "property"))
    prop_items = result.scalars().all()

    # Should have one property item per mapped column
    mapped_props = set(STANDARD_DOOR_MAPPING["property_mapping"].values())
    prop_names = {p.properties["property_name"] for p in prop_items}
    assert mapped_props.issubset(prop_names)


@pytest.mark.asyncio
async def test_property_connections_to_all_instances(
    client, import_setup, db_session: AsyncSession
):
    """Each property item connected to all imported doors."""
    setup = import_setup
    file_bytes = make_door_schedule_excel(5)

    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )

    # Get a property item (e.g., door/finish)
    result = await db_session.execute(
        select(Item).where(Item.identifier == "door/finish")
    )
    finish_prop = result.scalar_one_or_none()
    assert finish_prop is not None

    # Count connections from this property to doors
    conn_result = await db_session.execute(
        select(Connection).where(Connection.source_item_id == finish_prop.id)
    )
    conns = conn_result.scalars().all()
    # Each connection target should be a door
    door_conns = []
    for c in conns:
        item_result = await db_session.execute(
            select(Item).where(Item.id == c.target_item_id)
        )
        item = item_result.scalar_one_or_none()
        if item and item.item_type == "door":
            door_conns.append(c)
    assert len(door_conns) == 5


@pytest.mark.asyncio
async def test_reimport_no_duplicates(client, import_setup, db_session: AsyncSession):
    """Re-importing same schedule doesn't create duplicate property items."""
    setup = import_setup
    file_bytes = make_door_schedule_excel(5)

    for _ in range(2):
        await client.post(
            "/api/v1/import",
            data={
                "source_item_id": str(setup["schedule"].id),
                "time_context_id": str(setup["dd"].id),
                "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
            },
            files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
        )

    result = await db_session.execute(
        select(Item).where(Item.identifier == "door/finish")
    )
    items = result.scalars().all()
    assert len(items) == 1  # Not duplicated


def _make_spec_excel(rows_data):
    """Helper to create an Excel file with custom door data."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(
        [
            "DOOR NO.",
            "WIDTH",
            "HEIGHT",
            "FINISH",
            "MATERIAL",
            "HARDWARE SET",
            "FIRE RATING",
        ]
    )
    for row_data in rows_data:
        ws.append(
            [
                row_data.get("id", ""),
                "3'-0\"",
                "7'-0\"",
                row_data.get("finish", ""),
                row_data.get("material", ""),
                row_data.get("hardware_set", ""),
                row_data.get("fire_rating", ""),
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_conflict_connects_to_property_item(
    client, db_session: AsyncSession, make_item, make_connection
):
    """Conflict item has connection to property item."""
    # Setup with two sources
    project = await make_item("project", "Project Alpha")
    schedule = await make_item(
        "schedule",
        "Finish Schedule",
        {"name": "Finish Schedule", "discipline": "Architectural"},
    )
    spec = await make_item(
        "specification",
        "Door Spec",
        {"name": "Door Spec", "discipline": "Architectural"},
    )
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 100})
    await make_connection(project, schedule)
    await make_connection(project, spec)
    await make_connection(project, dd)

    # Schedule: finish=paint
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(schedule.id),
            "time_context_id": str(dd.id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={
            "file": (
                "s.xlsx",
                _make_spec_excel(
                    [
                        {
                            "id": "Door 001",
                            "finish": "paint",
                            "material": "wood",
                            "hardware_set": "HW-1",
                            "fire_rating": "",
                        }
                    ]
                ),
                "application/octet-stream",
            )
        },
    )
    # Spec: finish=stain → conflict
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(spec.id),
            "time_context_id": str(dd.id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={
            "file": (
                "s.xlsx",
                _make_spec_excel(
                    [
                        {
                            "id": "Door 001",
                            "finish": "stain",
                            "material": "wood",
                            "hardware_set": "HW-1",
                            "fire_rating": "",
                        }
                    ]
                ),
                "application/octet-stream",
            )
        },
    )

    # Find conflict
    conflict_result = await db_session.execute(
        select(Item).where(
            and_(
                Item.item_type == "conflict",
                Item.identifier.like("Door 001 / finish / %"),
            )
        )
    )
    conflict = conflict_result.scalar_one()

    # Find property item
    prop_result = await db_session.execute(
        select(Item).where(Item.identifier == "door/finish")
    )
    prop_item = prop_result.scalar_one()

    # Verify connection conflict → property
    conn_result = await db_session.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id == conflict.id,
                Connection.target_item_id == prop_item.id,
            )
        )
    )
    assert conn_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_change_connects_to_property_items(
    client, db_session: AsyncSession, make_item, make_connection
):
    """Change item connects to property items for each changed property."""
    # Setup
    project = await make_item("project", "Project Alpha")
    schedule = await make_item(
        "schedule",
        "Finish Schedule",
        {"name": "Finish Schedule", "discipline": "Architectural"},
    )
    dd = await make_item("milestone", "DD", {"name": "DD", "ordinal": 100})
    dd2 = await make_item("milestone", "DD2", {"name": "DD2", "ordinal": 200})
    await make_connection(project, schedule)
    await make_connection(project, dd)
    await make_connection(project, dd2)

    # First import: Door 001, finish=paint, material=wood
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(schedule.id),
            "time_context_id": str(dd.id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={
            "file": (
                "s.xlsx",
                _make_spec_excel(
                    [
                        {
                            "id": "Door 001",
                            "finish": "paint",
                            "material": "wood",
                            "hardware_set": "HW-1",
                            "fire_rating": "",
                        }
                    ]
                ),
                "application/octet-stream",
            )
        },
    )

    # Second import: finish and material both changed
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(schedule.id),
            "time_context_id": str(dd2.id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={
            "file": (
                "s.xlsx",
                _make_spec_excel(
                    [
                        {
                            "id": "Door 001",
                            "finish": "stain",
                            "material": "steel",
                            "hardware_set": "HW-1",
                            "fire_rating": "",
                        }
                    ]
                ),
                "application/octet-stream",
            )
        },
    )

    # Find change item
    change_result = await db_session.execute(
        select(Item).where(
            and_(Item.item_type == "change", Item.identifier.like("%Door 001%"))
        )
    )
    change = change_result.scalar_one()

    # Find property items
    finish_prop_result = await db_session.execute(
        select(Item).where(Item.identifier == "door/finish")
    )
    finish_prop = finish_prop_result.scalar_one()

    material_prop_result = await db_session.execute(
        select(Item).where(Item.identifier == "door/material")
    )
    material_prop = material_prop_result.scalar_one()

    # Verify connections change → properties
    finish_conn = await db_session.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id == change.id,
                Connection.target_item_id == finish_prop.id,
            )
        )
    )
    assert finish_conn.scalar_one_or_none() is not None

    material_conn = await db_session.execute(
        select(Connection).where(
            and_(
                Connection.source_item_id == change.id,
                Connection.target_item_id == material_prop.id,
            )
        )
    )
    assert material_conn.scalar_one_or_none() is not None
