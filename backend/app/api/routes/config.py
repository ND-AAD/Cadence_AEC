"""Configuration API routes — Type configuration and milestone templates."""

from fastapi import APIRouter

from app.core.type_config import ITEM_TYPES

router = APIRouter()


# ─── Type Configuration ────────────────────────────────────────

@router.get("/types")
async def get_type_config():
    """
    Get the complete type configuration.

    Returns all registered item types with their properties, valid targets,
    and other metadata used by the UI for rendering and validation.
    """
    return {
        name: {
            "label": cfg.label,
            "plural_label": cfg.plural_label,
            "category": cfg.category,
            "icon": cfg.icon,
            "color": cfg.color,
            "navigable": cfg.navigable,
            "is_source_type": cfg.is_source_type,
            "is_context_type": cfg.is_context_type,
            "valid_targets": cfg.valid_targets,
            "properties": [
                {
                    "name": p.name,
                    "label": p.label,
                    "data_type": p.data_type,
                    "required": p.required,
                    "unit": p.unit,
                    "enum_values": p.enum_values,
                }
                for p in cfg.properties
            ],
        }
        for name, cfg in ITEM_TYPES.items()
    }


# ─── Milestone Template ────────────────────────────────────────

@router.get("/milestone-template")
async def get_milestone_template():
    """
    Get the standard AEC milestone ordinals per Decision 3.

    Returns the project phase milestones with their ordinal sequence numbers
    (100–700) used for chronological ordering and navigation.
    """
    return {
        "milestones": [
            {
                "name": "Concept",
                "ordinal": 100,
            },
            {
                "name": "SD — Schematic Design",
                "ordinal": 200,
            },
            {
                "name": "DD — Design Development",
                "ordinal": 300,
            },
            {
                "name": "CD — Construction Documents",
                "ordinal": 400,
            },
            {
                "name": "Bidding",
                "ordinal": 500,
            },
            {
                "name": "CA — Construction Administration",
                "ordinal": 600,
            },
            {
                "name": "Closeout / Post-Occupancy",
                "ordinal": 700,
            },
        ]
    }
