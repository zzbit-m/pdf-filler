from pathlib import Path

import pytest

from app.services.pdf_preview import PREVIEW_DPI, pixel_to_point, render_preview


def test_render_preview(sample_pdf: Path) -> None:
    result = render_preview(sample_pdf, 0)
    assert result["page_number"] == 0
    assert result["width"] > 0
    assert result["height"] > 0
    assert result["dpi"] == PREVIEW_DPI


def test_render_with_cache(sample_pdf: Path, tmp_path: Path) -> None:
    result = render_preview(sample_pdf, 0, cache_dir=tmp_path)
    assert "image_path" in result
    assert Path(result["image_path"]).exists()


def test_render_out_of_range(sample_pdf: Path) -> None:
    with pytest.raises(ValueError, match="out of range"):
        render_preview(sample_pdf, 999)


def test_pixel_to_point() -> None:
    assert pixel_to_point(100, 150) == pytest.approx(48.0)
    assert pixel_to_point(0, 150) == 0
    assert pixel_to_point(150, 150) == 72.0


def test_pixel_to_point_default_dpi() -> None:
    assert pixel_to_point(150) == 72.0


def test_invalid_pdf(tmp_path: Path) -> None:
    bad_path = tmp_path / "not_a.pdf"
    bad_path.write_text("not a PDF", encoding="utf-8")
    with pytest.raises(Exception):
        render_preview(bad_path, 0)
