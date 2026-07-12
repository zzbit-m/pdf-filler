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
    font_name = "FillCustom"

    doc = fitz.open(pdf_path)
    try:
        doc[0].insert_font(fontfile=font_path_str, fontname=font_name)
        for pn in range(1, doc.page_count):
            doc[pn].insert_font(fontfile=font_path_str, fontname=font_name)

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
            text_rotate = page.rotation

            if max_width:
                half_h = font_size * 0.75
                rect = fitz.Rect(x, y - half_h, x + max_width, y + half_h)
                page.insert_textbox(rect, text, fontname=font_name,
                                    fontsize=font_size, color=(0, 0, 0),
                                    rotate=text_rotate, align=fitz.TEXT_ALIGN_LEFT)
            else:
                half_fs = font_size * 0.5
                if text_rotate == 90:
                    bx, by = x + half_fs, y
                elif text_rotate == 180:
                    bx, by = x, y - half_fs
                elif text_rotate == 270:
                    bx, by = x - half_fs, y
                else:
                    bx, by = x, y + half_fs
                point = fitz.Point(bx, by)
                page.insert_text(point, text, fontname=font_name,
                                 fontsize=font_size, color=(0, 0, 0),
                                 rotate=text_rotate)
            fields_placed += 1

        doc.save(str(output_path))
        return fields_placed
    finally:
        doc.close()
