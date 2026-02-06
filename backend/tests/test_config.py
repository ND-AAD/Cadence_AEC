"""Tests for Configuration API — Type config and milestone templates."""

import pytest


# ─── Type Configuration Endpoint ───────────────────────────────

@pytest.mark.asyncio
async def test_type_config_endpoint_returns_all_types(client):
    """Type config endpoint returns all registered types with properties."""
    response = await client.get("/api/v1/config/types")
    assert response.status_code == 200
    data = response.json()

    # All types should be present
    assert "project" in data
    assert "building" in data
    assert "floor" in data
    assert "room" in data
    assert "door" in data
    assert "schedule" in data
    assert "specification" in data
    assert "milestone" in data
    assert "phase" in data
    assert "change" in data
    assert "conflict" in data
    assert "decision" in data
    assert "note" in data

    # All type entries should have expected keys
    for type_name, type_config in data.items():
        assert "label" in type_config
        assert "plural_label" in type_config
        assert "category" in type_config
        assert "icon" in type_config
        assert "color" in type_config
        assert "navigable" in type_config
        assert "is_source_type" in type_config
        assert "is_context_type" in type_config
        assert "valid_targets" in type_config
        assert "render_mode" in type_config
        assert "default_sort" in type_config
        assert "search_fields" in type_config
        assert "exclude_from_conflicts" in type_config
        assert "properties" in type_config
        assert isinstance(type_config["properties"], list)
        assert isinstance(type_config["search_fields"], list)
        assert type_config["render_mode"] in ("table", "cards", "list", "timeline")


@pytest.mark.asyncio
async def test_door_type_has_expected_properties(client):
    """Door type has width, height, frame, hardware, and other properties."""
    response = await client.get("/api/v1/config/types")
    assert response.status_code == 200
    data = response.json()

    door_config = data["door"]

    # Verify door properties
    property_names = {p["name"] for p in door_config["properties"]}
    assert "mark" in property_names
    assert "width" in property_names
    assert "height" in property_names
    assert "type" in property_names
    assert "hardware_set" in property_names
    assert "fire_rating" in property_names
    assert "frame_type" in property_names
    assert "glazing" in property_names

    # Verify width and height are numeric
    width_prop = next(p for p in door_config["properties"] if p["name"] == "width")
    height_prop = next(p for p in door_config["properties"] if p["name"] == "height")
    assert width_prop["data_type"] == "number"
    assert height_prop["data_type"] == "number"
    assert width_prop["unit"] == "in"
    assert height_prop["unit"] == "in"


@pytest.mark.asyncio
async def test_type_config_includes_all_categories(client):
    """Types span all categories: spatial, document, temporal, workflow, organization."""
    response = await client.get("/api/v1/config/types")
    assert response.status_code == 200
    data = response.json()

    categories = {cfg["category"] for cfg in data.values()}
    assert "spatial" in categories
    assert "document" in categories
    assert "temporal" in categories
    assert "workflow" in categories
    assert "organization" in categories


@pytest.mark.asyncio
async def test_schedule_is_source_type(client):
    """Schedule type has is_source_type=True."""
    response = await client.get("/api/v1/config/types")
    assert response.status_code == 200
    data = response.json()

    schedule_config = data["schedule"]
    assert schedule_config["is_source_type"] is True


@pytest.mark.asyncio
async def test_milestone_is_context_type(client):
    """Milestone type has is_context_type=True."""
    response = await client.get("/api/v1/config/types")
    assert response.status_code == 200
    data = response.json()

    milestone_config = data["milestone"]
    assert milestone_config["is_context_type"] is True


@pytest.mark.asyncio
async def test_milestone_is_navigable(client):
    """Milestones are navigable — you can drill into an issuance to see submitted items."""
    response = await client.get("/api/v1/config/types")
    assert response.status_code == 200
    data = response.json()

    assert data["milestone"]["navigable"] is True
    assert data["phase"]["navigable"] is True


@pytest.mark.asyncio
async def test_door_render_mode_is_table(client):
    """Door type renders as a table (tabular data with many properties)."""
    response = await client.get("/api/v1/config/types")
    assert response.status_code == 200
    data = response.json()

    assert data["door"]["render_mode"] == "table"
    assert data["room"]["render_mode"] == "cards"
    assert data["milestone"]["render_mode"] == "timeline"


@pytest.mark.asyncio
async def test_workflow_types_excluded_from_conflicts(client):
    """Workflow types (change, conflict, decision, note) are excluded from conflict detection."""
    response = await client.get("/api/v1/config/types")
    assert response.status_code == 200
    data = response.json()

    assert data["change"]["exclude_from_conflicts"] is True
    assert data["conflict"]["exclude_from_conflicts"] is True
    assert data["decision"]["exclude_from_conflicts"] is True
    assert data["note"]["exclude_from_conflicts"] is True

    # Document sources should NOT be excluded
    assert data["schedule"]["exclude_from_conflicts"] is False
    assert data["specification"]["exclude_from_conflicts"] is False
    assert data["drawing"]["exclude_from_conflicts"] is False


@pytest.mark.asyncio
async def test_search_fields_populated(client):
    """Types have search_fields configured for indexing."""
    response = await client.get("/api/v1/config/types")
    assert response.status_code == 200
    data = response.json()

    # Doors should be searchable by mark
    assert "mark" in data["door"]["search_fields"]
    # Rooms should be searchable by name and number
    assert "name" in data["room"]["search_fields"]
    assert "number" in data["room"]["search_fields"]
    # Schedules should be searchable by name
    assert "name" in data["schedule"]["search_fields"]


# ─── Milestone Template Endpoint ───────────────────────────────

@pytest.mark.asyncio
async def test_milestone_template_endpoint_exists(client):
    """Milestone template endpoint returns successfully."""
    response = await client.get("/api/v1/config/milestone-template")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_milestone_template_returns_standard_aec_phases(client):
    """Milestone template returns the standard AEC milestone ordinals."""
    response = await client.get("/api/v1/config/milestone-template")
    assert response.status_code == 200
    data = response.json()

    assert "milestones" in data
    milestones = data["milestones"]
    assert len(milestones) == 7

    # Extract ordinals and names for easier testing
    milestone_map = {m["ordinal"]: m["name"] for m in milestones}

    # Verify all standard phases and ordinals
    assert milestone_map[100] == "Concept"
    assert milestone_map[200] == "SD — Schematic Design"
    assert milestone_map[300] == "DD — Design Development"
    assert milestone_map[400] == "CD — Construction Documents"
    assert milestone_map[500] == "Bidding"
    assert milestone_map[600] == "CA — Construction Administration"
    assert milestone_map[700] == "Closeout / Post-Occupancy"


@pytest.mark.asyncio
async def test_milestone_template_ordinals_are_sequential(client):
    """Milestone ordinals are in 100-increment sequence."""
    response = await client.get("/api/v1/config/milestone-template")
    assert response.status_code == 200
    data = response.json()

    milestones = data["milestones"]
    ordinals = [m["ordinal"] for m in milestones]

    # Should be 100, 200, 300, 400, 500, 600, 700
    expected = [100, 200, 300, 400, 500, 600, 700]
    assert ordinals == expected


@pytest.mark.asyncio
async def test_milestone_template_has_required_fields(client):
    """Each milestone in template has name and ordinal."""
    response = await client.get("/api/v1/config/milestone-template")
    assert response.status_code == 200
    data = response.json()

    for milestone in data["milestones"]:
        assert "name" in milestone
        assert "ordinal" in milestone
        assert isinstance(milestone["name"], str)
        assert isinstance(milestone["ordinal"], int)
