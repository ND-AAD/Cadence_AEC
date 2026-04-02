"""Tests for dynamic type configuration (WP-DYN-1)."""

import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.core import Item, Connection
from app.models.infrastructure import User, Permission


# --- Fixtures ---------------------------------------------------------

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def test_user(db_session):
    """Ensure the test user exists for FK constraints."""
    user = User(
        id=TEST_USER_ID,
        email="test@test.com",
        name="Test User",
        password_hash="not-a-real-hash",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def firm(db_session, test_user):
    """Create a firm item with permission for the test user."""
    firm_item = Item(
        item_type="firm",
        identifier="Test Firm",
        properties={"name": "Test Firm"},
        created_by=TEST_USER_ID,
    )
    db_session.add(firm_item)
    await db_session.flush()
    await db_session.refresh(firm_item)

    perm = Permission(
        user_id=TEST_USER_ID,
        scope_item_id=firm_item.id,
        role="admin",
        can_resolve_conflicts=True,
        can_import=True,
        can_edit=True,
    )
    db_session.add(perm)
    await db_session.flush()

    return firm_item


# --- resolve_user_firm ------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_user_firm_creates_firm_if_missing(db_session, test_user):
    """If user has no firm, resolve_user_firm creates one."""
    from app.services.dynamic_types import resolve_user_firm

    firm = await resolve_user_firm(db_session, TEST_USER_ID)
    assert firm is not None
    assert firm.item_type == "firm"
    assert firm.created_by == TEST_USER_ID


@pytest.mark.asyncio
async def test_resolve_user_firm_creates_permission(db_session, test_user):
    """Auto-created firm has admin permission for the user."""
    from app.services.dynamic_types import resolve_user_firm

    firm = await resolve_user_firm(db_session, TEST_USER_ID)

    result = await db_session.execute(
        select(Permission).where(
            Permission.user_id == TEST_USER_ID,
            Permission.scope_item_id == firm.id,
        )
    )
    perm = result.scalar_one()
    assert perm.role == "admin"


@pytest.mark.asyncio
async def test_resolve_user_firm_returns_existing(db_session, firm):
    """If user already has a firm, returns it instead of creating a new one."""
    from app.services.dynamic_types import resolve_user_firm

    resolved = await resolve_user_firm(db_session, TEST_USER_ID)
    assert resolved.id == firm.id


@pytest.mark.asyncio
async def test_resolve_user_firm_idempotent(db_session, test_user):
    """Calling resolve_user_firm twice returns the same firm."""
    from app.services.dynamic_types import resolve_user_firm

    firm1 = await resolve_user_firm(db_session, TEST_USER_ID)
    firm2 = await resolve_user_firm(db_session, TEST_USER_ID)
    assert firm1.id == firm2.id


# --- create_type_definition -------------------------------------------


@pytest.mark.asyncio
async def test_create_type_definition(db_session, firm):
    """Creates a type_definition item connected to the firm."""
    from app.services.dynamic_types import create_type_definition

    tc = await create_type_definition(
        db_session,
        firm.id,
        type_name="hardware_set",
        label="Hardware Set",
        plural_label="Hardware Sets",
        property_defs=[
            {"name": "mark", "label": "Mark", "data_type": "string", "required": True},
            {"name": "manufacturer", "label": "Manufacturer", "data_type": "string"},
        ],
    )

    assert tc.name == "hardware_set"
    assert tc.label == "Hardware Set"
    assert tc.category == "spatial"
    assert tc.navigable is True
    assert tc.render_mode == "table"
    assert len(tc.properties) == 2
    assert tc.properties[0].name == "mark"
    assert tc.properties[0].required is True


@pytest.mark.asyncio
async def test_create_type_definition_creates_item_and_connection(db_session, firm):
    """The type_definition item exists in the DB and is connected to the firm."""
    from app.services.dynamic_types import create_type_definition

    await create_type_definition(
        db_session, firm.id,
        type_name="hardware_set",
        label="Hardware Set",
    )

    # Verify item exists
    result = await db_session.execute(
        select(Item).where(
            Item.item_type == "type_definition",
            Item.identifier == "hardware_set",
        )
    )
    item = result.scalar_one()
    assert item.properties["label"] == "Hardware Set"

    # Verify connection from firm
    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == firm.id,
            Connection.target_item_id == item.id,
        )
    )
    conn = result.scalar_one()
    assert conn is not None


@pytest.mark.asyncio
async def test_create_type_rejects_os_collision(db_session, firm):
    """Cannot create a type with the same name as an OS type."""
    from app.services.dynamic_types import create_type_definition

    with pytest.raises(ValueError, match="OS type"):
        await create_type_definition(
            db_session, firm.id,
            type_name="conflict",
            label="Conflict",
        )


@pytest.mark.asyncio
async def test_create_type_rejects_duplicate(db_session, firm):
    """Cannot create two types with the same name under one firm."""
    from app.services.dynamic_types import create_type_definition

    await create_type_definition(
        db_session, firm.id,
        type_name="hardware_set",
        label="Hardware Set",
    )

    with pytest.raises(ValueError, match="already exists"):
        await create_type_definition(
            db_session, firm.id,
            type_name="hardware_set",
            label="Hardware Set 2",
        )


@pytest.mark.asyncio
async def test_create_type_defaults(db_session, firm):
    """New types get sensible defaults for spatial vocabulary."""
    from app.services.dynamic_types import create_type_definition

    tc = await create_type_definition(
        db_session, firm.id,
        type_name="curtain_wall",
        label="Curtain Wall",
    )

    assert tc.category == "spatial"
    assert tc.navigable is True
    assert tc.render_mode == "table"
    assert tc.exclude_from_conflicts is False
    assert tc.is_source_type is False
    assert tc.is_context_type is False


# --- get_firm_types ---------------------------------------------------


@pytest.mark.asyncio
async def test_get_firm_types_empty(db_session, firm):
    """Firm with no type definitions returns empty dict."""
    from app.services.dynamic_types import get_firm_types

    types = await get_firm_types(db_session, firm.id)
    assert types == {}


@pytest.mark.asyncio
async def test_get_firm_types_returns_created_types(db_session, firm):
    """Returns type definitions created for this firm."""
    from app.services.dynamic_types import create_type_definition, get_firm_types

    await create_type_definition(
        db_session, firm.id,
        type_name="hardware_set",
        label="Hardware Set",
        property_defs=[{"name": "mark", "label": "Mark"}],
    )

    types = await get_firm_types(db_session, firm.id)
    assert "hardware_set" in types
    assert types["hardware_set"].label == "Hardware Set"
    assert len(types["hardware_set"].properties) == 1


# --- get_merged_registry ----------------------------------------------


@pytest.mark.asyncio
async def test_get_merged_registry_includes_os_and_firm_types(db_session, firm):
    """Merged registry contains both OS types and firm types."""
    from app.services.dynamic_types import create_type_definition, get_merged_registry

    await create_type_definition(
        db_session, firm.id,
        type_name="hardware_set",
        label="Hardware Set",
    )

    merged = await get_merged_registry(db_session, firm.id)

    # OS types present
    assert "project" in merged
    assert "conflict" in merged
    assert "milestone" in merged

    # Firm type present
    assert "hardware_set" in merged


@pytest.mark.asyncio
async def test_merged_registry_os_wins_collision(db_session, firm):
    """If a firm type somehow has the same name as an OS type, OS wins."""
    from app.services.dynamic_types import get_merged_registry
    from app.core.type_config import ITEM_TYPES

    # Manually create a type_definition with an OS name (bypassing validation)
    rogue = Item(
        item_type="type_definition",
        identifier="milestone",
        properties={"label": "Rogue Milestone", "type_name": "milestone"},
    )
    db_session.add(rogue)
    await db_session.flush()
    await db_session.refresh(rogue)
    conn = Connection(source_item_id=firm.id, target_item_id=rogue.id)
    db_session.add(conn)
    await db_session.flush()

    merged = await get_merged_registry(db_session, firm.id)
    # OS version wins
    assert merged["milestone"].label == ITEM_TYPES["milestone"].label


# --- update_type_definition -------------------------------------------


@pytest.mark.asyncio
async def test_update_type_definition(db_session, firm):
    """Can update label and properties of a firm type."""
    from app.services.dynamic_types import create_type_definition, update_type_definition

    await create_type_definition(
        db_session, firm.id,
        type_name="hardware_set",
        label="Hardware Set",
    )

    tc = await update_type_definition(
        db_session, firm.id,
        type_name="hardware_set",
        label="Hardware Sets (Updated)",
        property_defs=[{"name": "series", "label": "Series"}],
    )

    assert tc.label == "Hardware Sets (Updated)"
    assert len(tc.properties) == 1
    assert tc.properties[0].name == "series"


@pytest.mark.asyncio
async def test_update_rejects_os_type(db_session, firm):
    """Cannot update an OS type."""
    from app.services.dynamic_types import update_type_definition

    with pytest.raises(ValueError, match="OS type"):
        await update_type_definition(
            db_session, firm.id,
            type_name="milestone",
            label="My Milestone",
        )


# --- delete_type_definition -------------------------------------------


@pytest.mark.asyncio
async def test_delete_type_definition(db_session, firm):
    """Can delete a firm type definition."""
    from app.services.dynamic_types import create_type_definition, delete_type_definition, get_firm_types

    await create_type_definition(
        db_session, firm.id,
        type_name="hardware_set",
        label="Hardware Set",
    )

    await delete_type_definition(db_session, firm.id, "hardware_set")

    types = await get_firm_types(db_session, firm.id)
    assert "hardware_set" not in types


@pytest.mark.asyncio
async def test_delete_rejects_os_type(db_session, firm):
    """Cannot delete an OS type."""
    from app.services.dynamic_types import delete_type_definition

    with pytest.raises(ValueError, match="OS type"):
        await delete_type_definition(db_session, firm.id, "milestone")


@pytest.mark.asyncio
async def test_delete_rejects_if_items_exist(db_session, firm):
    """Cannot delete a type if items of that type exist."""
    from app.services.dynamic_types import create_type_definition, delete_type_definition

    await create_type_definition(
        db_session, firm.id,
        type_name="hardware_set",
        label="Hardware Set",
    )

    # Create an item of that type
    hw_item = Item(
        item_type="hardware_set",
        identifier="HW-001",
        properties={},
    )
    db_session.add(hw_item)
    await db_session.flush()

    with pytest.raises(ValueError, match="items exist"):
        await delete_type_definition(db_session, firm.id, "hardware_set")


# --- seed_firm_types --------------------------------------------------


@pytest.mark.asyncio
async def test_seed_firm_types(db_session, firm):
    """Seeding creates starter catalog types as type_definition items."""
    from app.services.dynamic_types import seed_firm_types, get_firm_types

    seeded = await seed_firm_types(db_session, firm.id)
    assert len(seeded) > 0

    types = await get_firm_types(db_session, firm.id)
    # Should have at least door, room, building from the catalog
    assert "door" in types
    assert "room" in types
    assert "building" in types


@pytest.mark.asyncio
async def test_seed_idempotent(db_session, firm):
    """Seeding twice doesn't duplicate types."""
    from app.services.dynamic_types import seed_firm_types, get_firm_types

    await seed_firm_types(db_session, firm.id)
    count1 = len(await get_firm_types(db_session, firm.id))

    await seed_firm_types(db_session, firm.id)
    count2 = len(await get_firm_types(db_session, firm.id))

    assert count1 == count2


@pytest.mark.asyncio
async def test_seed_preserves_properties(db_session, firm):
    """Seeded types have full property definitions from the catalog."""
    from app.services.dynamic_types import seed_firm_types, get_firm_types

    await seed_firm_types(db_session, firm.id)
    types = await get_firm_types(db_session, firm.id)

    # Door should have its full property set
    door = types["door"]
    prop_names = {p.name for p in door.properties}
    assert "mark" in prop_names
    assert "width" in prop_names
    assert "height" in prop_names
    assert "hardware_set" in prop_names

    # Width should have unit and normalization
    width = next(p for p in door.properties if p.name == "width")
    assert width.unit == "in"
    assert width.data_type == "number"


# ─── DYN-2: API Routes ───────────────────────────────────────


@pytest.mark.asyncio
async def test_api_create_type(client):
    """POST /v1/types creates a type definition for the user's firm."""
    response = await client.post("/api/v1/types", json={
        "type_name": "hardware_set",
        "label": "Hardware Set",
        "plural_label": "Hardware Sets",
        "property_defs": [
            {"name": "mark", "label": "Mark", "required": True},
            {"name": "manufacturer", "label": "Manufacturer"},
        ],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "hardware_set"
    assert data["label"] == "Hardware Set"
    assert len(data["properties"]) == 2


@pytest.mark.asyncio
async def test_api_create_type_validation(client):
    """POST /v1/types with missing required fields returns 422."""
    response = await client.post("/api/v1/types", json={
        "label": "Missing Type Name",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_create_type_os_collision(client):
    """POST /v1/types with OS type name returns 409."""
    response = await client.post("/api/v1/types", json={
        "type_name": "conflict",
        "label": "Conflict",
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_api_list_types_merged(client):
    """GET /v1/types returns OS types + firm types merged."""
    # Create a firm type first
    await client.post("/api/v1/types", json={
        "type_name": "hardware_set",
        "label": "Hardware Set",
    })

    response = await client.get("/api/v1/types")
    assert response.status_code == 200
    data = response.json()

    # OS types present
    assert "project" in data
    assert "milestone" in data
    assert "conflict" in data

    # Firm type present
    assert "hardware_set" in data
    assert data["hardware_set"]["label"] == "Hardware Set"


@pytest.mark.asyncio
async def test_api_get_single_type(client):
    """GET /v1/types/{type_name} returns a single type config."""
    await client.post("/api/v1/types", json={
        "type_name": "hardware_set",
        "label": "Hardware Set",
    })

    response = await client.get("/api/v1/types/hardware_set")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "hardware_set"
    assert data["label"] == "Hardware Set"


@pytest.mark.asyncio
async def test_api_get_single_type_os(client):
    """GET /v1/types/{type_name} works for OS types too."""
    response = await client.get("/api/v1/types/milestone")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "milestone"
    assert data["is_context_type"] is True


@pytest.mark.asyncio
async def test_api_get_single_type_404(client):
    """GET /v1/types/{type_name} returns 404 for unknown type."""
    response = await client.get("/api/v1/types/nonexistent_type")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_update_type(client):
    """PATCH /v1/types/{type_name} updates a firm type."""
    await client.post("/api/v1/types", json={
        "type_name": "hardware_set",
        "label": "Hardware Set",
    })

    response = await client.patch("/api/v1/types/hardware_set", json={
        "label": "Hardware Sets (Updated)",
        "property_defs": [{"name": "series", "label": "Series"}],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "Hardware Sets (Updated)"
    assert len(data["properties"]) == 1


@pytest.mark.asyncio
async def test_api_update_os_type_rejected(client):
    """PATCH /v1/types/{type_name} for an OS type returns 403."""
    response = await client.patch("/api/v1/types/milestone", json={
        "label": "My Milestone",
    })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_delete_type(client):
    """DELETE /v1/types/{type_name} removes a firm type."""
    await client.post("/api/v1/types", json={
        "type_name": "hardware_set",
        "label": "Hardware Set",
    })

    response = await client.delete("/api/v1/types/hardware_set")
    assert response.status_code == 204

    # Verify it's gone
    response = await client.get("/api/v1/types/hardware_set")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_delete_os_type_rejected(client):
    """DELETE /v1/types/{type_name} for an OS type returns 403."""
    response = await client.delete("/api/v1/types/milestone")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_seed_types(client):
    """POST /v1/types/seed populates the user's firm with starter vocabulary."""
    response = await client.post("/api/v1/types/seed")
    assert response.status_code == 200
    data = response.json()
    assert data["seeded_count"] > 0

    # Verify types are now available
    response = await client.get("/api/v1/types")
    types = response.json()
    assert "door" in types
    assert "room" in types
    assert "building" in types


@pytest.mark.asyncio
async def test_api_seed_idempotent(client):
    """POST /v1/types/seed twice doesn't duplicate types."""
    response1 = await client.post("/api/v1/types/seed")
    count1 = response1.json()["seeded_count"]

    response2 = await client.post("/api/v1/types/seed")
    count2 = response2.json()["seeded_count"]

    assert count1 > 0
    assert count2 == 0  # Nothing new to seed
