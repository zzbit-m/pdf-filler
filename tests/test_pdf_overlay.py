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


def _build_pdf_with_rotation(rotation: int, tmp_path: Path) -> Path:
    path = tmp_path / f"rot_{rotation}.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=500)
    page.set_rotation(rotation)
    doc.save(str(path))
    doc.close()
    return path


def test_text_horizontal_on_rotated_page(tmp_path: Path) -> None:
    """Text on rotated pages must appear horizontal in the visual frame."""
    font_path = get_font_path()
    for rotation in [0, 90, 180, 270]:
        pdf = _build_pdf_with_rotation(rotation, tmp_path)
        out = tmp_path / f"filled_rot_{rotation}.pdf"
        fields = [
            {"column": "name", "page": 0, "x": 200, "y": 250, "font_size": 14},
        ]
        overlay_fields(pdf, fields, {"name": "REF"}, out, font_path)

        doc = fitz.open(out)
        try:
            page = doc[0]
            assert page.rotation == rotation

            pix = page.get_pixmap(dpi=150)
            w, h = pix.width, pix.height

            text_y_extent: list[int] = []
            for y in range(h):
                for x in range(w):
                    pixel = pix.pixel(x, y)
                    if isinstance(pixel, tuple) and pixel[0] < 100:
                        text_y_extent.append(y)
                        break

            assert text_y_extent, f"rot={rotation}: no text pixels found"
            y_spread = max(text_y_extent) - min(text_y_extent)
            text_height_pix = 14 * 150 / 72
            assert y_spread < text_height_pix * 2.5, (
                f"rot={rotation}: text spans y={min(text_y_extent)}..{max(text_y_extent)} "
                f"(spread {y_spread}), expected roughly one line height ({text_height_pix:.0f})"
            )
        finally:
            doc.close()
