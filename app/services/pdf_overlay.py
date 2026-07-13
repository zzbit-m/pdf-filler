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
        if doc.page_count == 0:
            return 0
        doc[0].insert_font(fontfile=font_path_str, fontname=font_name)
        for pn in range(1, doc.page_count):
            doc[pn].insert_font(fontfile=font_path_str, fontname=font_name)

        font_obj = fitz.Font(fontfile=font_path_str)
        fields_placed = 0
        for field in fields:
            is_text = field.get("type") == "text"
            if is_text:
                text = field.get("text_value", "")
                if not text:
                    continue
                pages_to_render = list(range(doc.page_count))
            else:
                col = field["column"]
                if col not in data or not data[col]:
                    continue
                text = data[col]
                page_num = field["page"]
                if page_num < 0 or page_num >= doc.page_count:
                    continue
                pages_to_render = [page_num]

            x = field["x"]
            y = field["y"]
            font_size = field.get("font_size", 11)
            max_width = field.get("max_width")

            for pn in pages_to_render:
                page = doc[pn]
                text_rotate = page.rotation

                if max_width:
                    half_h = font_size * 0.75
                    rect = fitz.Rect(x - max_width / 2, y - half_h,
                                     x + max_width / 2, y + half_h)
                    page.insert_textbox(rect, text, fontname=font_name,
                                        fontsize=font_size, color=(0, 0, 0),
                                        rotate=text_rotate, align=fitz.TEXT_ALIGN_CENTER)
                else:
                    tw = font_obj.text_length(text, fontsize=font_size)
                    if text_rotate == 90:
                        bx, by = x, y + tw / 2
                    elif text_rotate == 180:
                        bx, by = x + tw / 2, y
                    elif text_rotate == 270:
                        bx, by = x, y - tw / 2
                    else:
                        bx, by = x - tw / 2, y
                    point = fitz.Point(bx, by)
                    page.insert_text(point, text, fontname=font_name,
                                     fontsize=font_size, color=(0, 0, 0),
                                     rotate=text_rotate)

                fields_placed += 1

        doc.save(str(output_path))
        return fields_placed
    finally:
        doc.close()
