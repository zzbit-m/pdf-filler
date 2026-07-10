from pathlib import Path
from typing import Any

import fitz

PREVIEW_DPI = 150


def render_preview(
    pdf_path: str | Path,
    page_number: int,
    dpi: int = PREVIEW_DPI,
    cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    try:
        if page_number < 0 or page_number >= doc.page_count:
            raise ValueError(f"Page {page_number} out of range (0-{doc.page_count - 1})")

        page = doc[page_number]
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)

        result: dict[str, Any] = {
            "width": pix.width,
            "height": pix.height,
            "page_number": page_number,
            "dpi": dpi,
        }

        if cache_dir:
            cache_path = Path(cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)
            image_path = cache_path / f"page_{page_number}.png"
            pix.save(str(image_path))
            result["image_path"] = str(image_path)

        return result
    finally:
        doc.close()


def pixel_to_point(pixel: float, dpi: int = PREVIEW_DPI) -> float:
    return pixel * 72 / dpi
