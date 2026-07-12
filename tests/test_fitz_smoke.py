from pathlib import Path

import fitz
import pytest

from app.config import DATA_BASE

PDF_NAME = "0B2D03E1CCD3E3F41C1AFEA2510D5B1CD8C4C6FF_แบบฟอร์มใบลงทะเบียนอบรมปฐมนิเทศพนักงานใหม่.pdf"
PDF = str(Path("reference-files") / PDF_NAME)


@pytest.mark.skipif(not Path(PDF).exists(), reason="Reference PDF not available")
def test_pdf_can_open() -> None:
    doc = fitz.open(PDF)
    assert doc.page_count > 0
    doc.close()


@pytest.mark.skipif(not Path(PDF).exists(), reason="Reference PDF not available")
def test_render_preview() -> None:
    doc = fitz.open(PDF)
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    assert pix.width > 0
    assert pix.height > 0
    doc.close()


@pytest.mark.skipif(not Path(PDF).exists(), reason="Reference PDF not available")
def test_overlay_thai_text() -> None:
    doc = fitz.open(PDF)
    page = doc[0]
    page.insert_text(fitz.Point(100, 300), "ทดสอบชื่อพนักงาน", fontsize=12, color=(0, 0, 0))
    output = DATA_BASE / "output" / "test_overlay.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output))
    assert output.exists()
    doc.close()
