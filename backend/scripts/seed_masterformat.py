"""
MasterFormat hierarchy seeding — WP-14.

Seeds Division 08 (Openings) and Division 09 (Finishes) as spec_section
items in the three-table graph.  These provide the structural bridge
between specification-level assertions and element-level assertions.

Hierarchy levels:
  0 — Division     (e.g., "08")
  1 — Group        (e.g., "08 10 00")
  2 — Section      (e.g., "08 11 00")

Connection pattern:
  specification → division → group → section

Usage:
  Called from seed_data.py with a specification item UUID.
  Or standalone: python -m scripts.seed_masterformat
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.core import Connection, Item  # noqa: F401
from app.models.infrastructure import User  # noqa: F401


# ─── MasterFormat Data ────────────────────────────────────────

# Structure: (identifier, title, level, children)
# Level 0 = Division, Level 1 = Group, Level 2 = Section

DIVISION_08: list[tuple[str, str, list[tuple[str, str, list[tuple[str, str]]]]]] = [
    # (group_id, group_title, [(section_id, section_title), ...])
    (
        "08 10 00",
        "Doors and Frames",
        [
            ("08 11 00", "Metal Doors and Frames"),
            ("08 12 00", "Metal Frames"),
            ("08 13 00", "Metal Doors"),
            ("08 14 00", "Wood Doors"),
            ("08 16 00", "Composite Doors"),
        ],
    ),
    (
        "08 30 00",
        "Specialty Doors and Frames",
        [
            ("08 31 00", "Access Doors and Panels"),
            ("08 32 00", "Sliding Glass Doors"),
            ("08 34 00", "Special Function Doors"),
        ],
    ),
    (
        "08 40 00",
        "Entrances, Storefronts, and Curtain Walls",
        [
            ("08 41 00", "Entrances and Storefronts"),
            ("08 44 00", "Curtain Wall and Glazed Assemblies"),
        ],
    ),
    (
        "08 50 00",
        "Windows",
        [
            ("08 51 00", "Metal Windows"),
            ("08 52 00", "Wood Windows"),
            ("08 53 00", "Plastic Windows"),
        ],
    ),
    (
        "08 70 00",
        "Hardware",
        [
            ("08 71 00", "Door Hardware"),
            ("08 79 00", "Hardware Accessories"),
        ],
    ),
    (
        "08 80 00",
        "Glazing",
        [
            ("08 81 00", "Glass Glazing"),
            ("08 88 00", "Special Function Glazing"),
        ],
    ),
]

DIVISION_09: list[tuple[str, str, list[tuple[str, str, list[tuple[str, str]]]]]] = [
    (
        "09 20 00",
        "Plaster and Gypsum Board",
        [
            ("09 21 00", "Plaster and Gypsum Board Assemblies"),
            ("09 29 00", "Gypsum Board"),
        ],
    ),
    (
        "09 30 00",
        "Tiling",
        [
            ("09 31 00", "Thin-Set Tiling"),
        ],
    ),
    (
        "09 50 00",
        "Ceilings",
        [
            ("09 51 00", "Acoustical Ceilings"),
        ],
    ),
    (
        "09 60 00",
        "Flooring",
        [
            ("09 65 00", "Resilient Flooring"),
            ("09 68 00", "Carpeting"),
        ],
    ),
    (
        "09 90 00",
        "Painting and Coating",
        [
            ("09 91 00", "Painting"),
            ("09 93 00", "Staining and Transparent Finishing"),
            ("09 96 00", "High-Performance Coatings"),
        ],
    ),
]


# ─── Seed Function ────────────────────────────────────────────


async def seed_masterformat(
    db: AsyncSession,
    specification_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    """
    Seed MasterFormat hierarchy for Division 08 and 09.

    Creates spec_section items and wires them:
      specification → division → group → section

    Args:
        db: Active async database session.
        specification_id: UUID of the existing specification item
            to connect divisions to.

    Returns:
        Dict mapping section identifiers to UUIDs.
    """
    ids: dict[str, uuid.UUID] = {}

    def make_section(identifier: str, title: str, division: str, level: int) -> Item:
        item = Item(
            item_type="spec_section",
            identifier=identifier,
            properties={
                "title": title,
                "division": division,
                "level": level,
            },
        )
        db.add(item)
        return item

    def connect(source_id: uuid.UUID, target: Item) -> Connection:
        conn = Connection(
            source_item_id=source_id,
            target_item_id=target.id,
            properties={},
        )
        db.add(conn)
        return conn

    # ── Division 08: Openings ─────────────────────────────────
    div_08 = make_section("08", "Openings", "08", level=0)
    await db.flush()
    ids["08"] = div_08.id

    # Connect specification → Division 08
    connect(specification_id, div_08)

    for group_id, group_title, sections in DIVISION_08:
        group = make_section(group_id, group_title, "08", level=1)
        await db.flush()
        ids[group_id] = group.id

        # Division → Group
        connect(div_08.id, group)

        for section_id, section_title in sections:
            section = make_section(section_id, section_title, "08", level=2)
            await db.flush()
            ids[section_id] = section.id

            # Group → Section
            connect(group.id, section)

    # ── Division 09: Finishes ─────────────────────────────────
    div_09 = make_section("09", "Finishes", "09", level=0)
    await db.flush()
    ids["09"] = div_09.id

    # Connect specification → Division 09
    connect(specification_id, div_09)

    for group_id, group_title, sections in DIVISION_09:
        group = make_section(group_id, group_title, "09", level=1)
        await db.flush()
        ids[group_id] = group.id

        # Division → Group
        connect(div_09.id, group)

        for section_id, section_title in sections:
            section = make_section(section_id, section_title, "09", level=2)
            await db.flush()
            ids[section_id] = section.id

            # Group → Section
            connect(group.id, section)

    await db.flush()

    # Summary
    total_sections = len(ids)
    divisions = sum(1 for k in ids if len(k) == 2)
    groups = sum(1 for k in ids if len(k) == 8 and k.endswith("00"))
    leaves = total_sections - divisions - groups

    print(f"Seeded MasterFormat hierarchy:")
    print(f"  Divisions:  {divisions}")
    print(f"  Groups:     {groups}")
    print(f"  Sections:   {leaves}")
    print(f"  Total:      {total_sections}")

    return ids


# ─── CLI entry point ──────────────────────────────────────────


async def main():
    """Standalone seeding — creates a minimal specification item first."""
    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        async with session.begin():
            # Create a placeholder specification if running standalone
            spec = Item(
                item_type="specification",
                identifier="Spec §08 — Openings",
                properties={"name": "Specification Section 08 — Openings"},
            )
            session.add(spec)
            await session.flush()

            ids = await seed_masterformat(session, specification_id=spec.id)

    await engine.dispose()
    print("\nMasterFormat seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
