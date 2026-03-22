"""
Tests for WP-14: MasterFormat Hierarchy Seeding.

Covers:
  - spec_section type registration
  - Division 08 and 09 hierarchy creation
  - Section identifiers match MasterFormat numbering
  - Hierarchical connections: specification → division → group → section
  - Level properties (0=division, 1=group, 2=section)
  - Navigation API traversal of hierarchy
  - Integration with seed_project (Project Alpha)
"""

import pytest
from sqlalchemy import select, func

from app.models.core import Connection, Item
from app.core.type_config import get_type_config, ITEM_TYPES
from scripts.seed_data import seed_project
from scripts.seed_masterformat import seed_masterformat


# ─── Type Registration ────────────────────────────────────────


def test_spec_section_type_registered():
    """spec_section type exists in the type registry."""
    assert "spec_section" in ITEM_TYPES


def test_spec_section_type_config():
    """spec_section type has correct configuration."""
    tc = get_type_config("spec_section")
    assert tc is not None
    assert tc.category == "document"
    assert tc.navigable is True
    assert tc.is_source_type is False  # Sections are structural, not sources
    assert tc.exclude_from_conflicts is True
    assert "spec_section" in tc.valid_targets  # Self-referential for hierarchy


def test_spec_section_has_expected_properties():
    """spec_section type has title, division, and level properties."""
    tc = get_type_config("spec_section")
    prop_names = {p.name for p in tc.properties}
    assert "title" in prop_names
    assert "division" in prop_names
    assert "level" in prop_names


# ─── Standalone Seed ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_creates_two_divisions(db_session, make_item):
    """MasterFormat seed creates Division 08 and 09."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    assert "08" in ids
    assert "09" in ids

    # Verify they're actual items with correct properties
    for div_id in ("08", "09"):
        result = await db_session.execute(select(Item).where(Item.id == ids[div_id]))
        item = result.scalar_one()
        assert item.item_type == "spec_section"
        assert item.identifier == div_id
        assert item.properties["level"] == 0


@pytest.mark.asyncio
async def test_division_08_title(db_session, make_item):
    """Division 08 has title 'Openings'."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    result = await db_session.execute(select(Item).where(Item.id == ids["08"]))
    div_08 = result.scalar_one()
    assert div_08.properties["title"] == "Openings"


@pytest.mark.asyncio
async def test_division_09_title(db_session, make_item):
    """Division 09 has title 'Finishes'."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    result = await db_session.execute(select(Item).where(Item.id == ids["09"]))
    div_09 = result.scalar_one()
    assert div_09.properties["title"] == "Finishes"


@pytest.mark.asyncio
async def test_total_section_count(db_session, make_item):
    """Seed creates expected total spec_section items."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    result = await db_session.execute(
        select(func.count(Item.id)).where(Item.item_type == "spec_section")
    )
    count = result.scalar()
    # 2 divisions + 11 groups + 26 sections = 39
    assert count == 39
    assert len(ids) == 39


@pytest.mark.asyncio
async def test_key_sections_exist(db_session, make_item):
    """Key MasterFormat sections required by WP-14 exist."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    # Division 08 key sections
    assert "08 11 00" in ids  # Metal Doors and Frames
    assert "08 14 00" in ids  # Wood Doors
    assert "08 71 00" in ids  # Door Hardware
    assert "08 81 00" in ids  # Glass Glazing

    # Division 09 key sections
    assert "09 91 00" in ids  # Painting
    assert "09 93 00" in ids  # Staining


@pytest.mark.asyncio
async def test_section_identifiers_match_masterformat(db_session, make_item):
    """All spec_section identifiers follow MasterFormat numbering format."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    await seed_masterformat(db_session, specification_id=spec.id)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "spec_section")
    )
    sections = result.scalars().all()

    for section in sections:
        identifier = section.identifier
        level = section.properties.get("level")

        if level == 0:
            # Division: two-digit code
            assert len(identifier) == 2, (
                f"Division identifier '{identifier}' should be 2 chars"
            )
        elif level in (1, 2):
            # Group/Section: "XX XX XX" format
            parts = identifier.split(" ")
            assert len(parts) == 3, (
                f"Section identifier '{identifier}' should have 3 parts"
            )
            assert all(len(p) == 2 for p in parts), (
                f"Section identifier '{identifier}' parts should be 2 chars each"
            )


# ─── Hierarchy Connections ────────────────────────────────────


@pytest.mark.asyncio
async def test_specification_connects_to_divisions(db_session, make_item):
    """Specification item connects to both divisions."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    # spec → Division 08
    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == spec.id,
            Connection.target_item_id == ids["08"],
        )
    )
    assert result.scalar_one_or_none() is not None

    # spec → Division 09
    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == spec.id,
            Connection.target_item_id == ids["09"],
        )
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_division_connects_to_groups(db_session, make_item):
    """Division 08 connects to its groups."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    div_08_id = ids["08"]

    # Count outgoing connections from Division 08 to spec_sections
    result = await db_session.execute(
        select(func.count(Connection.id))
        .select_from(Connection)
        .join(Item, Connection.target_item_id == Item.id)
        .where(
            Connection.source_item_id == div_08_id,
            Item.item_type == "spec_section",
        )
    )
    count = result.scalar()
    # Division 08 has 6 groups
    assert count == 6


@pytest.mark.asyncio
async def test_group_connects_to_sections(db_session, make_item):
    """Group 08 10 00 (Doors and Frames) connects to its sections."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    group_id = ids["08 10 00"]

    # Count outgoing connections from group to spec_sections
    result = await db_session.execute(
        select(func.count(Connection.id))
        .select_from(Connection)
        .join(Item, Connection.target_item_id == Item.id)
        .where(
            Connection.source_item_id == group_id,
            Item.item_type == "spec_section",
        )
    )
    count = result.scalar()
    # 08 10 00 has 5 sections: 08 11 00, 08 12 00, 08 13 00, 08 14 00, 08 16 00
    assert count == 5


@pytest.mark.asyncio
async def test_hierarchy_traversal_spec_to_section(db_session, make_item):
    """Can traverse specification → Division 08 → 08 10 00 → 08 11 00."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    # Step 1: spec → divisions
    result = await db_session.execute(
        select(Connection.target_item_id).where(Connection.source_item_id == spec.id)
    )
    division_ids = {row[0] for row in result.all()}
    assert ids["08"] in division_ids

    # Step 2: Division 08 → groups
    result = await db_session.execute(
        select(Connection.target_item_id).where(Connection.source_item_id == ids["08"])
    )
    group_ids = {row[0] for row in result.all()}
    assert ids["08 10 00"] in group_ids

    # Step 3: Group 08 10 00 → sections
    result = await db_session.execute(
        select(Connection.target_item_id).where(
            Connection.source_item_id == ids["08 10 00"]
        )
    )
    section_ids = {row[0] for row in result.all()}
    assert ids["08 11 00"] in section_ids


# ─── Level Properties ────────────────────────────────────────


@pytest.mark.asyncio
async def test_level_0_items_are_divisions(db_session, make_item):
    """Level 0 items are exactly the 2 divisions."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    await seed_masterformat(db_session, specification_id=spec.id)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "spec_section")
    )
    all_sections = result.scalars().all()

    level_0 = [s for s in all_sections if s.properties.get("level") == 0]
    assert len(level_0) == 2
    assert {s.identifier for s in level_0} == {"08", "09"}


@pytest.mark.asyncio
async def test_level_1_items_are_groups(db_session, make_item):
    """Level 1 items are groups (XX XX 00 format)."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    await seed_masterformat(db_session, specification_id=spec.id)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "spec_section")
    )
    all_sections = result.scalars().all()

    level_1 = [s for s in all_sections if s.properties.get("level") == 1]
    # Div 08: 6 groups, Div 09: 5 groups = 11 groups
    assert len(level_1) == 11

    # All groups should have "00" as the last two digits
    for group in level_1:
        assert group.identifier.endswith("00"), (
            f"Group '{group.identifier}' should end with '00'"
        )


@pytest.mark.asyncio
async def test_level_2_items_are_sections(db_session, make_item):
    """Level 2 items are leaf sections."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    await seed_masterformat(db_session, specification_id=spec.id)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "spec_section")
    )
    all_sections = result.scalars().all()

    level_2 = [s for s in all_sections if s.properties.get("level") == 2]
    # 17 sections in Div 08, 9 sections in Div 09 = 26
    assert len(level_2) == 26


@pytest.mark.asyncio
async def test_division_property_correct(db_session, make_item):
    """All sections have the correct division property."""
    spec = await make_item("specification", "Test Spec", {"name": "Test Spec"})
    await seed_masterformat(db_session, specification_id=spec.id)

    result = await db_session.execute(
        select(Item).where(Item.item_type == "spec_section")
    )
    all_sections = result.scalars().all()

    for section in all_sections:
        div = section.properties.get("division")
        # Division property should match the first 2 chars of identifier
        if section.properties.get("level") == 0:
            assert div == section.identifier
        else:
            assert div == section.identifier[:2], (
                f"Section '{section.identifier}' has division '{div}', expected '{section.identifier[:2]}'"
            )


# ─── Integration with seed_project ───────────────────────────


@pytest.mark.asyncio
async def test_seed_project_includes_masterformat(db_session):
    """seed_project now includes MasterFormat hierarchy."""
    ids = await seed_project(db_session)

    # Should have MasterFormat section IDs
    assert "08" in ids
    assert "09" in ids
    assert "08 11 00" in ids


@pytest.mark.asyncio
async def test_seed_project_spec_connects_to_divisions(db_session):
    """Project Alpha's specification connects to MasterFormat divisions."""
    ids = await seed_project(db_session)

    spec_id = ids["spec"]
    div_08_id = ids["08"]

    result = await db_session.execute(
        select(Connection).where(
            Connection.source_item_id == spec_id,
            Connection.target_item_id == div_08_id,
        )
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_seed_project_spec_section_count(db_session):
    """Project Alpha seed includes all MasterFormat sections."""
    await seed_project(db_session)

    result = await db_session.execute(
        select(func.count(Item.id)).where(Item.item_type == "spec_section")
    )
    count = result.scalar()
    assert count == 39


# ─── Navigation API Integration ──────────────────────────────


@pytest.mark.asyncio
async def test_navigate_spec_to_divisions(
    client, db_session, make_item, make_connection
):
    """GET /items/:spec_id/connected returns divisions as connected items."""
    spec = await make_item("specification", "Nav Spec", {"name": "Nav Spec"})
    await seed_masterformat(db_session, specification_id=spec.id)

    response = await client.get(f"/api/v1/items/{spec.id}/connected?types=spec_section")
    assert response.status_code == 200
    data = response.json()

    # Should have a "spec_section" group in connected
    section_groups = [g for g in data["connected"] if g["item_type"] == "spec_section"]
    assert len(section_groups) == 1
    # The spec directly connects to 2 divisions
    assert section_groups[0]["count"] == 2


@pytest.mark.asyncio
async def test_navigate_division_to_groups(client, db_session, make_item):
    """GET /items/:division_id/connected returns groups."""
    spec = await make_item("specification", "Nav Spec", {"name": "Nav Spec"})
    ids = await seed_masterformat(db_session, specification_id=spec.id)

    div_08_id = ids["08"]

    response = await client.get(
        f"/api/v1/items/{div_08_id}/connected?types=spec_section"
    )
    assert response.status_code == 200
    data = response.json()

    section_groups = [g for g in data["connected"] if g["item_type"] == "spec_section"]
    assert len(section_groups) == 1
    # Division 08 has 6 groups
    assert section_groups[0]["count"] == 6
