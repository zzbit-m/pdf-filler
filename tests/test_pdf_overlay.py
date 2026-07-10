from pathlib import Path

import fitz

from app.services.font_loader import get_font_path
from app.services.pdf_overlay import overlay_fields


def test_overlay_fields(sample_pdf: Path, sample_font: str, tmp_path: Path) -> None:
    fields = [
        {"column": "Name", "page": 0, "x": 100, "y": 200, "font_size": 12},
        {"column": "Position", "page": 0, "x": 100, "y": 220, "font_size": 11},
    ]
    data = {"Name": "John Doe", "Position": "Engineer"}
    output = tmp_path / "output.pdf"

    count = overlay_fields(sample_pdf, fields, data, output, sample_font)
    assert count == 2
    assert output.exists()


def test_skip_empty_value(sample_pdf: Path, sample_font: str, tmp_path: Path) -> None:
    fields = [
        {"column": "Name", "page": 0, "x": 100, "y": 200, "font_size": 12},
        {"column": "Position", "page": 0, "x": 100, "y": 220, "font_size": 11},
    ]
    data = {"Name": "", "Position": "Engineer"}
    output = tmp_path / "output.pdf"

    count = overlay_fields(sample_pdf, fields, data, output, sample_font)
    assert count == 1


def test_skip_missing_column(sample_pdf: Path, sample_font: str, tmp_path: Path) -> None:
    fields = [
        {"column": "MissingCol", "page": 0, "x": 100, "y": 200, "font_size": 12},
    ]
    data = {"Name": "John Doe"}
    output = tmp_path / "output.pdf"

    count = overlay_fields(sample_pdf, fields, data, output, sample_font)
    assert count == 0


def test_skip_out_of_range_page(sample_pdf: Path, sample_font: str, tmp_path: Path) -> None:
    fields = [
        {"column": "Name", "page": 999, "x": 100, "y": 200, "font_size": 12},
    ]
    data = {"Name": "John Doe"}
    output = tmp_path / "output.pdf"

    count = overlay_fields(sample_pdf, fields, data, output, sample_font)
    assert count == 0


def test_overlay_with_max_width(sample_pdf: Path, sample_font: str, tmp_path: Path) -> None:
    fields = [
        {"column": "Name", "page": 0, "x": 100, "y": 200, "font_size": 11, "max_width": 150},
    ]
    data = {"Name": "John Doe Very Long Name That Might Wrap"}
    output = tmp_path / "output.pdf"

    count = overlay_fields(sample_pdf, fields, data, output, sample_font)
    assert count == 1


def test_thai_text_rendering(sample_pdf: Path, tmp_path: Path) -> None:
    font_path = get_font_path()
    fields = [
        {"column": "Name", "page": 0, "x": 100, "y": 200, "font_size": 14},
    ]
    data = {"Name": "สวัสดีชาวโลก"}
    output = tmp_path / "thai_output.pdf"
    input_size = sample_pdf.stat().st_size

    count = overlay_fields(sample_pdf, fields, data, output, font_path)
    assert count == 1
    assert output.exists()
    assert output.stat().st_size > input_size

    doc = fitz.open(output)
    try:
        page = doc[0]
        blocks = page.get_text("blocks")
        assert len(blocks) > 0
    finally:
        doc.close()
