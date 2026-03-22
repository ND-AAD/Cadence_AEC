"""
Test PDF generation for WP-16: Specification Preprocessing.

Generates minimal valid PDFs with known MasterFormat section content
for testing the preprocessing pipeline.

Uses reportlab for PDF creation — lightweight and deterministic.
"""

import io
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


# ─── Standard Test Content ────────────────────────────────────────

SAMPLE_PART1_GENERAL = """\
PART 1 - GENERAL

1.01 SUMMARY
A. Section includes wood doors for interior and exterior applications.
B. Related Sections:
   1. Section 08 12 00 - Metal Frames
   2. Section 08 71 00 - Door Hardware

1.02 REFERENCES
A. AWI/AWMAC - Architectural Woodwork Standards
B. WDMA - Window and Door Manufacturers Association

1.03 SUBMITTALS
A. Product Data: Submit manufacturer's product data for each type of door.
B. Shop Drawings: Submit shop drawings showing door dimensions and details.
"""

SAMPLE_PART2_PRODUCTS = """\
PART 2 - PRODUCTS

2.01 MANUFACTURERS
A. Acceptable Manufacturers:
   1. Oshkosh Door Company
   2. VT Industries
   3. Marshfield Door Systems

2.02 WOOD DOORS
A. Interior Flush Doors:
   1. Core: Structural composite lumber core
   2. Face: Rotary-cut white maple veneer
   3. Edges: Hardwood edge strips
   4. Thickness: 1-3/4 inches
   5. Fire Rating: 20-minute where indicated

2.03 DOOR FRAMES
A. Material: Hollow metal frames per Section 08 12 00.

2.04 FINISHES
A. Factory finish: UV-cured polyurethane
B. Field finish: As specified in Section 09 93 00
"""

SAMPLE_PART3_EXECUTION = """\
PART 3 - EXECUTION

3.01 INSTALLATION
A. Install doors in accordance with manufacturer's recommendations.
B. Coordinate with frame installation.

3.02 ADJUSTING
A. Adjust doors for proper operation and clearance.

END OF SECTION
"""

SAMPLE_SECTION_08_14_00 = f"""\
SECTION 08 14 00 - WOOD DOORS

{SAMPLE_PART1_GENERAL}

{SAMPLE_PART2_PRODUCTS}

{SAMPLE_PART3_EXECUTION}
"""

SAMPLE_SECTION_08_11_00 = """\
SECTION 08 11 00 - METAL DOORS AND FRAMES

PART 1 - GENERAL

1.01 SUMMARY
A. Section includes hollow metal doors and frames.
B. Types: Standard duty, heavy duty, and fire-rated assemblies.

1.02 REFERENCES
A. SDI - Steel Door Institute
B. NFPA 80 - Standard for Fire Doors

PART 2 - PRODUCTS

2.01 MANUFACTURERS
A. Acceptable Manufacturers:
   1. Steelcraft
   2. Ceco Door
   3. Curries Company

2.02 HOLLOW METAL DOORS
A. Construction: Cold-rolled steel, flush design
B. Gauge: 16 gauge minimum
C. Core: Polyurethane insulated
D. Fire Rating: 90 minutes where indicated on drawings

2.03 HOLLOW METAL FRAMES
A. Construction: Cold-rolled steel
B. Gauge: 16 gauge
C. Type: Welded or knock-down as indicated

PART 3 - EXECUTION

3.01 INSTALLATION
A. Install in accordance with SDI-117 recommendations.
B. Coordinate with masonry and drywall work.

END OF SECTION
"""

SAMPLE_SECTION_08_71_00 = """\
SECTION 08 71 00 - DOOR HARDWARE

PART 1 - GENERAL

1.01 SUMMARY
A. Section includes door hardware for new doors.

PART 2 - PRODUCTS

2.01 MANUFACTURERS
A. Acceptable Manufacturers:
   1. Schlage
   2. Von Duprin
   3. LCN

2.02 HARDWARE SETS
A. Set 1: Office doors — lever lockset, closer, wall stop
B. Set 2: Corridor doors — lever passage set, closer, hold-open
C. Set 3: Rated doors — lever lockset, closer, coordinator

PART 3 - EXECUTION

3.01 INSTALLATION
A. Install hardware per manufacturer's templates and BHMA guidelines.

END OF SECTION
"""


# ─── PDF Generation ──────────────────────────────────────────────


def generate_spec_pdf(
    sections: list[dict[str, str]] | None = None,
    content: str | None = None,
) -> bytes:
    """
    Generate a minimal valid specification PDF.

    Args:
        sections: List of dicts with keys: "number", "title", "part1", "part2", "part3".
                  If provided, generates a multi-section document.
        content: Raw text content. If provided, generates a single-page PDF with this text.

    Returns:
        PDF file bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )

    styles = getSampleStyleSheet()

    # Add custom styles
    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=12,
    )
    part_header_style = ParagraphStyle(
        "PartHeader",
        parent=styles["Heading2"],
        fontSize=12,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "SpecBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
    )

    story = []

    if content:
        # Simple single-content PDF
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
            else:
                # Escape HTML entities for reportlab
                safe_line = (
                    line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                )
                story.append(Paragraph(safe_line, body_style))
                story.append(Spacer(1, 2))

    elif sections:
        for i, section in enumerate(sections):
            if i > 0:
                story.append(PageBreak())

            number = section.get("number", "00 00 00")
            title = section.get("title", "Unknown Section")
            safe_title = (
                title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )

            # Section header
            header_text = f"SECTION {number} - {safe_title}"
            story.append(Paragraph(header_text, section_header_style))
            story.append(Spacer(1, 12))

            # Part 1
            part1 = section.get(
                "part1", "PART 1 - GENERAL\n\n1.01 SUMMARY\nA. General requirements."
            )
            for line in part1.split("\n"):
                safe_line = (
                    line.strip()
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                if not safe_line:
                    story.append(Spacer(1, 4))
                elif safe_line.startswith("PART"):
                    story.append(Paragraph(safe_line, part_header_style))
                else:
                    story.append(Paragraph(safe_line, body_style))
                    story.append(Spacer(1, 2))

            story.append(Spacer(1, 8))

            # Part 2
            part2 = section.get(
                "part2", "PART 2 - PRODUCTS\n\n2.01 MATERIALS\nA. As specified."
            )
            for line in part2.split("\n"):
                safe_line = (
                    line.strip()
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                if not safe_line:
                    story.append(Spacer(1, 4))
                elif safe_line.startswith("PART"):
                    story.append(Paragraph(safe_line, part_header_style))
                else:
                    story.append(Paragraph(safe_line, body_style))
                    story.append(Spacer(1, 2))

            story.append(Spacer(1, 8))

            # Part 3
            part3 = section.get(
                "part3", "PART 3 - EXECUTION\n\n3.01 INSTALLATION\nA. Per manufacturer."
            )
            for line in part3.split("\n"):
                safe_line = (
                    line.strip()
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                if not safe_line:
                    story.append(Spacer(1, 4))
                elif safe_line.startswith("PART"):
                    story.append(Paragraph(safe_line, part_header_style))
                else:
                    story.append(Paragraph(safe_line, body_style))
                    story.append(Spacer(1, 2))

            # End of section marker
            story.append(Spacer(1, 12))
            story.append(Paragraph("END OF SECTION", body_style))
    else:
        # Empty document
        story.append(Paragraph("Specification Document", styles["Title"]))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def generate_single_section_pdf(
    section_number: str = "08 14 00",
    title: str = "WOOD DOORS",
) -> bytes:
    """Generate a PDF with a single specification section (08 14 00 by default)."""
    return generate_spec_pdf(
        sections=[
            {
                "number": section_number,
                "title": title,
                "part1": SAMPLE_PART1_GENERAL,
                "part2": SAMPLE_PART2_PRODUCTS,
                "part3": SAMPLE_PART3_EXECUTION,
            }
        ]
    )


def generate_multi_section_spec_pdf() -> bytes:
    """
    Generate a realistic Division 08 specification with 3 sections.

    Sections: 08 11 00, 08 14 00, 08 71 00
    """
    return generate_spec_pdf(
        sections=[
            {
                "number": "08 11 00",
                "title": "METAL DOORS AND FRAMES",
                "part1": "PART 1 - GENERAL\n\n1.01 SUMMARY\nA. Section includes hollow metal doors and frames.\nB. Types: Standard duty, heavy duty, and fire-rated assemblies.\n\n1.02 REFERENCES\nA. SDI - Steel Door Institute\nB. NFPA 80 - Standard for Fire Doors",
                "part2": "PART 2 - PRODUCTS\n\n2.01 MANUFACTURERS\nA. Steelcraft\nB. Ceco Door\nC. Curries Company\n\n2.02 HOLLOW METAL DOORS\nA. Construction: Cold-rolled steel, flush design\nB. Gauge: 16 gauge minimum\nC. Core: Polyurethane insulated\nD. Fire Rating: 90 minutes where indicated",
                "part3": "PART 3 - EXECUTION\n\n3.01 INSTALLATION\nA. Install in accordance with SDI-117 recommendations.\nB. Coordinate with masonry and drywall work.",
            },
            {
                "number": "08 14 00",
                "title": "WOOD DOORS",
                "part1": SAMPLE_PART1_GENERAL,
                "part2": SAMPLE_PART2_PRODUCTS,
                "part3": SAMPLE_PART3_EXECUTION,
            },
            {
                "number": "08 71 00",
                "title": "DOOR HARDWARE",
                "part1": "PART 1 - GENERAL\n\n1.01 SUMMARY\nA. Section includes door hardware for new doors.",
                "part2": "PART 2 - PRODUCTS\n\n2.01 MANUFACTURERS\nA. Schlage\nB. Von Duprin\nC. LCN\n\n2.02 HARDWARE SETS\nA. Set 1: Office doors\nB. Set 2: Corridor doors\nC. Set 3: Rated doors",
                "part3": "PART 3 - EXECUTION\n\n3.01 INSTALLATION\nA. Install hardware per manufacturer's templates.",
            },
        ]
    )


def generate_compressed_number_pdf() -> bytes:
    """Generate a PDF using compressed section numbers (e.g., '081400')."""
    content = """\
SECTION 081400 - WOOD DOORS

PART 1 - GENERAL

1.01 SUMMARY
A. This section includes wood doors.

PART 2 - PRODUCTS

2.01 MANUFACTURERS
A. VT Industries
B. Oshkosh Door Company

PART 3 - EXECUTION

3.01 INSTALLATION
A. Install per manufacturer recommendations.

END OF SECTION
"""
    return generate_spec_pdf(content=content)


def generate_no_parts_pdf() -> bytes:
    """Generate a PDF with a section but no PART markers."""
    content = """\
SECTION 08 14 00 - WOOD DOORS

SCOPE
This section covers wood doors for interior applications.

MANUFACTURERS
VT Industries, Oshkosh Door Company, Marshfield Door Systems.

MATERIALS
Core: Structural composite lumber.
Face: White maple veneer.
Thickness: 1-3/4 inches.

INSTALLATION
Install in accordance with manufacturer's recommendations.

END OF SECTION
"""
    return generate_spec_pdf(content=content)


def generate_empty_pdf() -> bytes:
    """Generate a valid but empty PDF (no specification content)."""
    return generate_spec_pdf(
        content="This document contains no specification sections."
    )
