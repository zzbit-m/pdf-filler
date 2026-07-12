import fitz
import pytest
from fastapi.testclient import TestClient

from app.config import DATA_BASE
from app.main import app
from app.services.pdf_preview import pixel_to_point

UPLOADS = DATA_BASE / "uploads"

client = TestClient(app)


def _upload_rotated_pdf(rotation: int) -> str:
    doc = fitz.open()
    page = doc.new_page(width=400, height=500)
    page.set_rotation(rotation)
    pdf_bytes = doc.write()
    doc.close()
    resp = client.post(
        "/upload/pdf",
        files={"file": (f"rot{rotation}.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["pdf_id"]


def _convert(
    px: float, py: float, rotation: int, media_w: float, media_h: float
) -> tuple[float, float]:
    if rotation == 90:
        return (media_w - py, media_h - px)
    elif rotation == 180:
        return (media_w - px, py)
    elif rotation == 270:
        return (py, px)
    else:
        return (px, media_h - py)


class TestRotationConversion:
    def test_rot0_roundtrip(self):
        pdf_id = _upload_rotated_pdf(0)
        doc = fitz.open(str(UPLOADS / f"{pdf_id}.pdf"))
        page = doc[0]
        media_w = page.mediabox_size.x
        media_h = page.mediabox_size.y
        doc.close()

        px_display, py_display = 100, 200
        px_pt = pixel_to_point(px_display)
        py_pt = pixel_to_point(py_display)
        x, y = _convert(px_pt, py_pt, 0, media_w, media_h)
        assert x == pytest.approx(px_pt)
        assert y == pytest.approx(media_h - py_pt)

    def test_rot90_roundtrip(self):
        pdf_id = _upload_rotated_pdf(90)
        doc = fitz.open(str(UPLOADS / f"{pdf_id}.pdf"))
        page = doc[0]
        dm = page.derotation_matrix
        rect_h = page.rect.height
        media_w = page.mediabox_size.x
        media_h = page.mediabox_size.y
        doc.close()

        a, b, c, d, e, f = dm
        px_display, py_display = 300, 150
        px_pt = pixel_to_point(px_display)
        py_pt = pixel_to_point(py_display)

        vx = px_pt
        vy = rect_h - py_pt
        expected_ux = a * vx + c * vy + e
        expected_uy = b * vx + d * vy + f

        x, y = _convert(px_pt, py_pt, 90, media_w, media_h)
        assert x == pytest.approx(expected_ux, abs=0.01)
        assert y == pytest.approx(expected_uy, abs=0.01)

    def test_rot180_roundtrip(self):
        pdf_id = _upload_rotated_pdf(180)
        doc = fitz.open(str(UPLOADS / f"{pdf_id}.pdf"))
        page = doc[0]
        dm = page.derotation_matrix
        rect_h = page.rect.height
        media_w = page.mediabox_size.x
        media_h = page.mediabox_size.y
        doc.close()

        a, b, c, d, e, f = dm
        px_display, py_display = 100, 100
        px_pt = pixel_to_point(px_display)
        py_pt = pixel_to_point(py_display)

        vx = px_pt
        vy = rect_h - py_pt
        expected_ux = a * vx + c * vy + e
        expected_uy = b * vx + d * vy + f

        x, y = _convert(px_pt, py_pt, 180, media_w, media_h)
        assert x == pytest.approx(expected_ux, abs=0.01)
        assert y == pytest.approx(expected_uy, abs=0.01)

    def test_rot270_roundtrip(self):
        pdf_id = _upload_rotated_pdf(270)
        doc = fitz.open(str(UPLOADS / f"{pdf_id}.pdf"))
        page = doc[0]
        dm = page.derotation_matrix
        rect_h = page.rect.height
        media_w = page.mediabox_size.x
        media_h = page.mediabox_size.y
        doc.close()

        a, b, c, d, e, f = dm
        px_display, py_display = 200, 350
        px_pt = pixel_to_point(px_display)
        py_pt = pixel_to_point(py_display)

        vx = px_pt
        vy = rect_h - py_pt
        expected_ux = a * vx + c * vy + e
        expected_uy = b * vx + d * vy + f

        x, y = _convert(px_pt, py_pt, 270, media_w, media_h)
        assert x == pytest.approx(expected_ux, abs=0.01)
        assert y == pytest.approx(expected_uy, abs=0.01)

    def test_all_rotations_deterministic(self):
        results = {}
        for rot in [0, 90, 180, 270]:
            pdf_id = _upload_rotated_pdf(rot)
            doc = fitz.open(str(UPLOADS / f"{pdf_id}.pdf"))
            page = doc[0]
            mw = page.mediabox_size.x
            mh = page.mediabox_size.y
            doc.close()

            px_pt = pixel_to_point(200)
            py_pt = pixel_to_point(300)
            x, y = _convert(px_pt, py_pt, rot, mw, mh)
            results[rot] = (x, y)

        assert results[0] != results[90]
        assert results[0] != results[180]
        assert results[0] != results[270]

