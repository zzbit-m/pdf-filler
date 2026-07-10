from pathlib import Path
from typing import Any

import fitz

from app.services.font_loader import get_font_path


def overlay_fields(
    pdf_path: str | Path,
    fields: list[dict[str, Any]],
    data: dict[str, str],
    output_path: str | Path,
    font_path: str | Path | None = None,
) -> int:
    if font_path is None:
        font_path = get_font_path()
    font_path_str = str(font_path)
    doc = fitz.open(pdf_path)
    try:
        fields_placed = 0
        for field in fields:
            col = field["column"]
            if col not in data or not data[col]:
                continue

            text = data[col]
            page_num = field["page"]
            if page_num < 0 or page_num >= doc.page_count:
                continue

            page = doc[page_num]
            x = field["x"]
            y = field["y"]
            font_size = field.get("font_size", 11)
            max_width = field.get("max_width")

            if max_width:
                rect = fitz.Rect(x, y, x + max_width, y + font_size * 1.5)
                page.insert_textbox(rect, text, fontfile=font_path_str, fontsize=font_size,
                                    color=(0, 0, 0))
            else:
                page.insert_text(
                    fitz.Point(x, y),
                    text,
                    fontfile=font_path_str,
                    fontsize=font_size,
                    color=(0, 0, 0),
                )
            fields_placed += 1

        doc.save(str(output_path))
        return fields_placed
    finally:
        doc.close()
