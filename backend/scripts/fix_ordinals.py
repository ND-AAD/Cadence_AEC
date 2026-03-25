"""
Diagnostic script for fixing milestone ordinals.

The resolved view filters snapshots with `snap_ordinal <= context_ordinal`.
When milestones have ordinal 0 (default when missing), all snapshots pass the
filter, causing future-milestone data to bleed into earlier views.

This script:
1. Identifies all milestone items with ordinal 0
2. Attempts to infer correct ordinals from identifier patterns (AEC phase codes)
3. Reports findings and optionally updates the database

Usage:
    python -m scripts.fix_ordinals          # Diagnostic report only
    python -m scripts.fix_ordinals --fix    # Apply fixes to database
"""

import asyncio
import re
import sys
from typing import Optional

from sqlalchemy import select

from app.core.database import async_session
from app.models.core import Item


# ─── AEC Phase Ordinals ─────────────────────────────────────────

AEC_PHASE_ORDINALS = {
    "SD": 200,  # Schematic Design
    "DD": 300,  # Design Development
    "CD": 400,  # Construction Documents
    "BID": 500,  # Bidding & Negotiation
    "CA": 600,  # Construction Administration
}


def compute_ordinal(milestone_name: str, milestone_identifier: str) -> Optional[int]:
    """
    Infer ordinal from milestone name or identifier using AEC phase patterns.

    Patterns recognized:
    - "Schematic Design" or "SD" -> 200
    - "Design Development" or "DD" -> 300
    - "Construction Documents" or "CD" -> 400
    - "Bidding & Negotiation" or "BID" -> 500
    - "Construction Administration" or "CA" -> 600

    Args:
        milestone_name: Name field from the milestone item
        milestone_identifier: Identifier field from the milestone item

    Returns:
        Inferred ordinal, or None if no pattern matches
    """
    combined = f"{milestone_name} {milestone_identifier}".upper()

    # Check for exact matches first (shorter strings take precedence)
    for phase_code, ordinal in sorted(
        AEC_PHASE_ORDINALS.items(), key=lambda x: -len(x[0])
    ):
        # Match as whole word (not substring of another word)
        if re.search(rf"\b{re.escape(phase_code)}\b", combined):
            return ordinal

    # Check for full phase names
    phase_names = {
        "SCHEMATIC DESIGN": 200,
        "DESIGN DEVELOPMENT": 300,
        "CONSTRUCTION DOCUMENTS": 400,
        "BIDDING": 500,
        "CONSTRUCTION ADMIN": 600,
    }
    for phase_name, ordinal in phase_names.items():
        if phase_name in combined:
            return ordinal

    return None


async def diagnose_and_fix(fix: bool = False) -> None:
    """
    Diagnose milestone ordinal issues and optionally fix them.

    Args:
        fix: If True, update the database. If False, only report.
    """
    async with async_session() as session:
        # Get all milestones with ordinal 0 (or missing)
        result = await session.execute(
            select(Item).where(Item.item_type == "milestone")
        )
        milestones = result.scalars().all()

        # Filter to those with ordinal 0
        ordinal_zero = [
            m for m in milestones if (m.properties or {}).get("ordinal", 0) == 0
        ]

        if not ordinal_zero:
            print("✓ All milestones have non-zero ordinals. No fixes needed.")
            return

        print(f"Found {len(ordinal_zero)} milestone(s) with ordinal 0:")
        print()

        fixes_applied = 0
        for milestone in ordinal_zero:
            inferred = compute_ordinal(
                milestone.properties.get("name", "") if milestone.properties else "",
                milestone.identifier,
            )

            if inferred:
                print(
                    f"  - {milestone.identifier} (ID: {milestone.id})"
                    f"\n    Name: {milestone.properties.get('name') if milestone.properties else 'N/A'}"
                    f"\n    Inferred ordinal: {inferred}"
                )
                if fix:
                    if not milestone.properties:
                        milestone.properties = {}
                    milestone.properties["ordinal"] = inferred
                    fixes_applied += 1
                    print("    ✓ Updated")
                else:
                    print("    (Would update if --fix passed)")
                print()
            else:
                print(
                    f"  - {milestone.identifier} (ID: {milestone.id})"
                    f"\n    Name: {milestone.properties.get('name') if milestone.properties else 'N/A'}"
                    f"\n    Could not infer ordinal. Manual intervention needed."
                    f"\n    (No pattern match for AEC phase codes: SD, DD, CD, BID, CA)"
                )
                print()

        if fix:
            await session.commit()
            print(f"✓ Applied {fixes_applied} fix(es) to the database.")
        else:
            print(
                f"Would apply {len([m for m in ordinal_zero if compute_ordinal(m.properties.get('name', '') if m.properties else '', m.identifier)])}"
                f" fix(es) if --fix passed."
            )


async def main():
    """Entry point for the diagnostic script."""
    fix = "--fix" in sys.argv

    if fix:
        print("Running ordinal fixer in UPDATE mode...")
    else:
        print("Running ordinal fixer in DIAGNOSTIC mode (no changes)...")

    print()
    await diagnose_and_fix(fix=fix)


if __name__ == "__main__":
    asyncio.run(main())
