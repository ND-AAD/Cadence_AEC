"""
Factory for generating test Excel and CSV files for import tests.

Creates realistic door schedule data matching Project Alpha seed structure.
"""

import csv
import io
from typing import Any

import openpyxl


def make_door_schedule_excel(
    num_doors: int = 50,
    identifier_prefix: str = "Door",
    extra_columns: dict[str, list[Any]] | None = None,
) -> bytes:
    """
    Generate a door schedule Excel file.

    Columns: DOOR NO., WIDTH, HEIGHT, FINISH, MATERIAL, HARDWARE SET, FIRE RATING
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Door Schedule"

    # Header row
    headers = [
        "DOOR NO.",
        "WIDTH",
        "HEIGHT",
        "FINISH",
        "MATERIAL",
        "HARDWARE SET",
        "FIRE RATING",
    ]
    if extra_columns:
        headers.extend(extra_columns.keys())

    ws.append(headers)

    # Data rows
    finishes = ["paint", "stain", "veneer", "laminate", "anodized"]
    materials = ["wood", "hollow metal", "aluminum", "fiberglass", "steel"]
    hardware_sets = [f"HW-{i}" for i in range(1, 11)]
    fire_ratings = ["", "20 min", "45 min", "60 min", "90 min"]

    for i in range(1, num_doors + 1):
        row = [
            f"{identifier_prefix} {i:03d}",  # DOOR NO.
            "3'-0\"",                          # WIDTH
            "7'-0\"",                          # HEIGHT
            finishes[i % len(finishes)],       # FINISH
            materials[i % len(materials)],     # MATERIAL
            hardware_sets[i % len(hardware_sets)],  # HARDWARE SET
            fire_ratings[i % len(fire_ratings)],    # FIRE RATING
        ]
        if extra_columns:
            for col_name, values in extra_columns.items():
                row.append(values[i % len(values)] if values else "")
        ws.append(row)

    # Save to bytes
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def make_door_schedule_csv(
    num_doors: int = 50,
    identifier_prefix: str = "Door",
) -> bytes:
    """Generate a door schedule CSV file."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    headers = [
        "DOOR NO.",
        "WIDTH",
        "HEIGHT",
        "FINISH",
        "MATERIAL",
        "HARDWARE SET",
        "FIRE RATING",
    ]
    writer.writerow(headers)

    finishes = ["paint", "stain", "veneer", "laminate", "anodized"]
    materials = ["wood", "hollow metal", "aluminum", "fiberglass", "steel"]
    hardware_sets = [f"HW-{i}" for i in range(1, 11)]
    fire_ratings = ["", "20 min", "45 min", "60 min", "90 min"]

    for i in range(1, num_doors + 1):
        row = [
            f"{identifier_prefix} {i:03d}",
            "3'-0\"",
            "7'-0\"",
            finishes[i % len(finishes)],
            materials[i % len(materials)],
            hardware_sets[i % len(hardware_sets)],
            fire_ratings[i % len(fire_ratings)],
        ]
        writer.writerow(row)

    return buf.getvalue().encode("utf-8")


def make_updated_door_schedule_excel(
    num_doors: int = 50,
    identifier_prefix: str = "Door",
    changed_finish: str = "stain",
    changed_indices: list[int] | None = None,
) -> bytes:
    """
    Generate an updated door schedule where some doors have changed finishes.

    Used for testing re-import and change detection.
    """
    if changed_indices is None:
        changed_indices = list(range(1, min(11, num_doors + 1)))  # First 10 doors

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Door Schedule"

    headers = [
        "DOOR NO.",
        "WIDTH",
        "HEIGHT",
        "FINISH",
        "MATERIAL",
        "HARDWARE SET",
        "FIRE RATING",
    ]
    ws.append(headers)

    finishes = ["paint", "stain", "veneer", "laminate", "anodized"]
    materials = ["wood", "hollow metal", "aluminum", "fiberglass", "steel"]
    hardware_sets = [f"HW-{i}" for i in range(1, 11)]
    fire_ratings = ["", "20 min", "45 min", "60 min", "90 min"]

    for i in range(1, num_doors + 1):
        finish = changed_finish if i in changed_indices else finishes[i % len(finishes)]
        row = [
            f"{identifier_prefix} {i:03d}",
            "3'-0\"",
            "7'-0\"",
            finish,
            materials[i % len(materials)],
            hardware_sets[i % len(hardware_sets)],
            fire_ratings[i % len(fire_ratings)],
        ]
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


STANDARD_DOOR_MAPPING = {
    "file_type": "excel",
    "identifier_column": "DOOR NO.",
    "target_item_type": "door",
    "header_row": 1,
    "property_mapping": {
        "WIDTH": "width",
        "HEIGHT": "height",
        "FINISH": "finish",
        "MATERIAL": "material",
        "HARDWARE SET": "hardware_set",
        "FIRE RATING": "fire_rating",
    },
    "normalizations": {},
}
