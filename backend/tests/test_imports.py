"""
Tests for WP-6: Import pipeline.

Covers:
  - Excel/CSV file parsing
  - Identifier matching (exact, normalized)
  - Snapshot creation via import (upsert semantics)
  - Connection creation (source → target)
  - Source self-snapshot
  - Import mapping CRUD
  - Re-import at same milestone (upsert, no duplicates)
  - Re-import at different milestone (new snapshots, old preserved)
  - Import batch tracking
"""

import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.core import Connection, Item, Snapshot
from tests.fixtures.excel_factory import (
    STANDARD_DOOR_MAPPING,
    make_door_schedule_csv,
    make_door_schedule_excel,
    make_updated_door_schedule_excel,
)


# ─── Helpers ──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def project_setup(make_item, make_connection):
    """
    Create a minimal project with source and milestones.

    Returns dict with: project, schedule, dd_milestone, cd_milestone
    """
    project = await make_item("project", "Project Alpha")
    schedule = await make_item(
        "schedule",
        "Finish Schedule",
        {"name": "Finish Schedule", "discipline": "Architectural"},
    )
    dd_milestone = await make_item(
        "milestone",
        "DD",
        {"name": "Design Development", "ordinal": 100},
    )
    cd_milestone = await make_item(
        "milestone",
        "CD",
        {"name": "Construction Documents", "ordinal": 200},
    )
    # Wire up connections
    await make_connection(project, schedule)
    await make_connection(project, dd_milestone)
    await make_connection(project, cd_milestone)
    return {
        "project": project,
        "schedule": schedule,
        "dd_milestone": dd_milestone,
        "cd_milestone": cd_milestone,
    }


# ─── Import Mapping CRUD ──────────────────────────────────────


@pytest.mark.asyncio
async def test_set_import_mapping(client: AsyncClient, project_setup):
    """PUT mapping on source item, then GET it back."""
    setup = project_setup
    source_id = str(setup["schedule"].id)

    # PUT mapping
    resp = await client.put(
        f"/api/v1/items/{source_id}/import-mapping",
        json=STANDARD_DOOR_MAPPING,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["identifier_column"] == "DOOR NO."
    assert data["target_item_type"] == "door"

    # GET mapping
    resp = await client.get(f"/api/v1/items/{source_id}/import-mapping")
    assert resp.status_code == 200
    data = resp.json()
    assert data["identifier_column"] == "DOOR NO."
    assert data["property_mapping"]["WIDTH"] == "width"


@pytest.mark.asyncio
async def test_get_import_mapping_when_none(client: AsyncClient, project_setup):
    """GET mapping when none has been stored returns null."""
    setup = project_setup
    resp = await client.get(
        f"/api/v1/items/{setup['schedule'].id}/import-mapping"
    )
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_set_mapping_invalid_type(client: AsyncClient, project_setup):
    """PUT mapping with unknown target type returns 400."""
    setup = project_setup
    mapping = {**STANDARD_DOOR_MAPPING, "target_item_type": "nonexistent_type"}
    resp = await client.put(
        f"/api/v1/items/{setup['schedule'].id}/import-mapping",
        json=mapping,
    )
    assert resp.status_code == 400
    assert "Unknown target item type" in resp.json()["detail"]


# ─── File Parsing (unit tests via service) ────────────────────


@pytest.mark.asyncio
async def test_parse_excel_50_doors():
    """Parse a 50-door Excel schedule and verify row count."""
    from app.schemas.imports import ImportMappingConfig
    from app.services.import_service import parse_excel

    file_bytes = make_door_schedule_excel(50)
    mapping = ImportMappingConfig(**STANDARD_DOOR_MAPPING)
    rows = parse_excel(file_bytes, mapping)

    assert len(rows) == 50
    # First door
    assert rows[0]["_identifier"] == "Door 001"
    assert rows[0]["_row_number"] == 2  # Row 1 is header
    assert "width" in rows[0]
    assert "finish" in rows[0]

    # Last door
    assert rows[49]["_identifier"] == "Door 050"


@pytest.mark.asyncio
async def test_parse_csv_50_doors():
    """Parse a 50-door CSV schedule."""
    from app.schemas.imports import ImportMappingConfig
    from app.services.import_service import parse_csv

    file_bytes = make_door_schedule_csv(50)
    mapping = ImportMappingConfig(
        **{**STANDARD_DOOR_MAPPING, "file_type": "csv"}
    )
    rows = parse_csv(file_bytes, mapping)

    assert len(rows) == 50
    assert rows[0]["_identifier"] == "Door 001"


@pytest.mark.asyncio
async def test_parse_excel_skips_empty_rows():
    """Rows with empty identifiers are skipped."""
    import io
    import openpyxl

    from app.schemas.imports import ImportMappingConfig
    from app.services.import_service import parse_excel

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DOOR NO.", "FINISH"])
    ws.append(["Door 001", "paint"])
    ws.append([None, "stain"])  # Empty identifier — should skip
    ws.append(["Door 003", "veneer"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    mapping = ImportMappingConfig(
        file_type="excel",
        identifier_column="DOOR NO.",
        target_item_type="door",
        header_row=1,
        property_mapping={"FINISH": "finish"},
    )
    rows = parse_excel(buf.getvalue(), mapping)
    assert len(rows) == 2
    assert rows[0]["_identifier"] == "Door 001"
    assert rows[1]["_identifier"] == "Door 003"


@pytest.mark.asyncio
async def test_parse_excel_with_normalization():
    """Normalizations specified in mapping are applied during parse."""
    import io
    import openpyxl

    from app.schemas.imports import ImportMappingConfig
    from app.services.import_service import parse_excel

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DOOR NO.", "FINISH"])
    ws.append(["Door 001", "PAINT"])
    ws.append(["Door 002", "  Stain  "])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    mapping = ImportMappingConfig(
        file_type="excel",
        identifier_column="DOOR NO.",
        target_item_type="door",
        header_row=1,
        property_mapping={"FINISH": "finish"},
        normalizations={"finish": "lowercase_trim"},
    )
    rows = parse_excel(buf.getvalue(), mapping)
    assert rows[0]["finish"] == "paint"
    assert rows[1]["finish"] == "stain"


# ─── Full Import Endpoint ─────────────────────────────────────


@pytest.mark.asyncio
async def test_import_50_door_schedule(client: AsyncClient, project_setup):
    """
    Import a 50-row door schedule at DD milestone.

    Acceptance criteria:
    - 50 door snapshots created, all attributed to schedule source
    - Source self-snapshot created
    - Connections created between schedule and each door
    """
    setup = project_setup
    file_bytes = make_door_schedule_excel(50)

    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("door_schedule.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 201
    result = resp.json()

    assert result["source_item_id"] == str(setup["schedule"].id)
    assert result["time_context_id"] == str(setup["dd_milestone"].id)

    summary = result["summary"]
    assert summary["items_imported"] == 50
    assert summary["items_created"] == 50  # All new items
    assert summary["snapshots_created"] == 50
    assert summary["connections_created"] == 50


@pytest.mark.asyncio
async def test_import_creates_source_self_snapshot(
    client: AsyncClient, project_setup, db_session
):
    """Import creates a source self-snapshot with metadata."""
    from sqlalchemy import select

    setup = project_setup
    file_bytes = make_door_schedule_excel(10)

    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )

    # Check source self-snapshot
    result = await db_session.execute(
        select(Snapshot).where(
            Snapshot.item_id == setup["schedule"].id,
            Snapshot.context_id == setup["dd_milestone"].id,
            Snapshot.source_id == setup["schedule"].id,
        )
    )
    self_snap = result.scalar_one_or_none()
    assert self_snap is not None
    assert self_snap.properties["row_count"] == 10
    assert "columns_mapped" in self_snap.properties


@pytest.mark.asyncio
async def test_reimport_same_milestone_upserts(client: AsyncClient, project_setup):
    """
    Re-import same file at same milestone → upserts (no duplicates).

    The second import should upsert existing snapshots, not create new ones.
    """
    setup = project_setup
    file_bytes = make_door_schedule_excel(10)
    import_data = {
        "source_item_id": str(setup["schedule"].id),
        "time_context_id": str(setup["dd_milestone"].id),
        "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
    }

    # First import
    resp1 = await client.post(
        "/api/v1/import",
        data=import_data,
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    assert resp1.status_code == 201
    s1 = resp1.json()["summary"]
    assert s1["items_created"] == 10
    assert s1["snapshots_created"] == 10

    # Second import (same file, same milestone)
    resp2 = await client.post(
        "/api/v1/import",
        data=import_data,
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    assert resp2.status_code == 201
    s2 = resp2.json()["summary"]
    assert s2["items_created"] == 0  # No new items
    assert s2["items_matched_exact"] == 10  # All matched exactly
    assert s2["snapshots_upserted"] == 10  # All upserted
    assert s2["snapshots_created"] == 0  # None new
    assert s2["connections_existing"] == 10  # All existing


@pytest.mark.asyncio
async def test_import_different_milestone_preserves_old(
    client: AsyncClient, project_setup, db_session
):
    """
    Second import with different milestone → new snapshots at new context,
    old ones preserved.
    """
    from sqlalchemy import func, select

    setup = project_setup
    file_bytes = make_door_schedule_excel(5)
    mapping = json.dumps(STANDARD_DOOR_MAPPING)

    # Import at DD
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": mapping,
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )

    # Import at CD
    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["cd_milestone"].id),
            "mapping_config": mapping,
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    assert resp.status_code == 201
    s = resp.json()["summary"]
    assert s["snapshots_created"] == 5  # New snapshots at CD

    # Verify DD snapshots still exist
    dd_count = await db_session.execute(
        select(func.count(Snapshot.id)).where(
            Snapshot.context_id == setup["dd_milestone"].id,
            Snapshot.source_id == setup["schedule"].id,
            Snapshot.item_id != setup["schedule"].id,  # Exclude self-snapshot
        )
    )
    assert dd_count.scalar() == 5  # DD snapshots preserved


@pytest.mark.asyncio
async def test_normalized_matching(client: AsyncClient, project_setup, make_item):
    """
    Normalized matching: "Door 101", "DOOR 101", "DR-101" patterns.

    Create items with varying identifiers, then import with the standard
    identifiers. Exact matches should find them; normalized matching handles
    case/whitespace.
    """
    setup = project_setup

    # Pre-create a door with different casing
    existing_door = await make_item("door", "door 001", {"mark": "001"})

    # Import with "Door 001" in the file — should normalize-match "door 001"
    file_bytes = make_door_schedule_excel(1)  # "Door 001"

    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    assert resp.status_code == 201
    s = resp.json()["summary"]
    # "Door 001" matches "door 001" via normalized matching
    assert s["items_matched_normalized"] == 1
    assert s["items_created"] == 0


@pytest.mark.asyncio
async def test_import_stores_mapping_on_source(
    client: AsyncClient, project_setup
):
    """Import stores the mapping config on the source item for reuse."""
    setup = project_setup
    file_bytes = make_door_schedule_excel(5)

    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )

    # Mapping should now be stored on the source
    resp = await client.get(
        f"/api/v1/items/{setup['schedule'].id}/import-mapping"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data is not None
    assert data["identifier_column"] == "DOOR NO."


@pytest.mark.asyncio
async def test_import_reuses_stored_mapping(client: AsyncClient, project_setup):
    """Second import can omit mapping_config if stored on source."""
    setup = project_setup
    file_bytes = make_door_schedule_excel(5)

    # First import with explicit mapping
    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )

    # Second import without mapping_config — should use stored
    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["cd_milestone"].id),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    assert resp.status_code == 201
    assert resp.json()["summary"]["items_imported"] == 5


@pytest.mark.asyncio
async def test_import_no_mapping_returns_400(client: AsyncClient, project_setup):
    """Import without mapping and no stored mapping → 400."""
    setup = project_setup
    file_bytes = make_door_schedule_excel(5)

    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert "No mapping configuration" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_import_invalid_context_type(client: AsyncClient, project_setup):
    """Import with non-milestone context returns 400."""
    setup = project_setup
    file_bytes = make_door_schedule_excel(5)

    # Use project (not a milestone) as context
    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["project"].id),  # Not a milestone!
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert "milestone" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_creates_batch_item(
    client: AsyncClient, project_setup, db_session
):
    """Import creates an import_batch item to track the operation."""
    from sqlalchemy import select

    setup = project_setup
    file_bytes = make_door_schedule_excel(10)

    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    batch_id = resp.json()["batch_id"]

    # Verify batch item exists
    result = await db_session.execute(
        select(Item).where(Item.id == uuid.UUID(batch_id))
    )
    batch = result.scalar_one_or_none()
    assert batch is not None
    assert batch.item_type == "import_batch"
    assert batch.properties["status"] == "completed"
    assert batch.properties["row_count"] == 10


@pytest.mark.asyncio
async def test_get_import_batch_status(client: AsyncClient, project_setup):
    """GET /import/:batch_id returns batch status."""
    setup = project_setup
    file_bytes = make_door_schedule_excel(5)

    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )
    batch_id = resp.json()["batch_id"]

    resp = await client.get(f"/api/v1/import/{batch_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["properties"]["status"] == "completed"


@pytest.mark.asyncio
async def test_import_csv_file(client: AsyncClient, project_setup):
    """Import a CSV file instead of Excel."""
    setup = project_setup
    file_bytes = make_door_schedule_csv(10)
    mapping = {**STANDARD_DOOR_MAPPING, "file_type": "csv"}

    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(mapping),
        },
        files={"file": ("schedule.csv", file_bytes, "text/csv")},
    )
    assert resp.status_code == 201
    assert resp.json()["summary"]["items_imported"] == 10


@pytest.mark.asyncio
async def test_import_empty_file(client: AsyncClient, project_setup):
    """Import with empty file returns 400."""
    setup = project_setup

    resp = await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("empty.xlsx", b"", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert "Empty file" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_import_snapshots_attributed_to_source(
    client: AsyncClient, project_setup, db_session
):
    """All created snapshots have source_id = schedule item."""
    from sqlalchemy import select

    setup = project_setup
    file_bytes = make_door_schedule_excel(5)

    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )

    # All snapshots for DD from this source
    result = await db_session.execute(
        select(Snapshot).where(
            Snapshot.context_id == setup["dd_milestone"].id,
            Snapshot.source_id == setup["schedule"].id,
        )
    )
    snaps = result.scalars().all()
    # 5 door snapshots + 1 self-snapshot = 6
    assert len(snaps) == 6
    for snap in snaps:
        assert snap.source_id == setup["schedule"].id
        assert snap.context_id == setup["dd_milestone"].id


@pytest.mark.asyncio
async def test_import_connections_direction(
    client: AsyncClient, project_setup, db_session
):
    """Connections go from source (schedule) → target (door)."""
    from sqlalchemy import select

    setup = project_setup
    file_bytes = make_door_schedule_excel(3)

    await client.post(
        "/api/v1/import",
        data={
            "source_item_id": str(setup["schedule"].id),
            "time_context_id": str(setup["dd_milestone"].id),
            "mapping_config": json.dumps(STANDARD_DOOR_MAPPING),
        },
        files={"file": ("schedule.xlsx", file_bytes, "application/octet-stream")},
    )

    # Check connections from schedule
    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == setup["schedule"].id
        )
    )
    conns = result.scalars().all()
    # 3 doors (project→schedule was created by fixture, not counted here
    # because it's source=project, not source=schedule)
    door_conns = [c for c in conns if c.target_item_id != setup["project"].id]
    assert len(door_conns) == 3

    # Verify targets are doors
    for conn in door_conns:
        target_result = await db_session.execute(
            select(Item).where(Item.id == conn.target_item_id)
        )
        target = target_result.scalar_one()
        assert target.item_type == "door"
