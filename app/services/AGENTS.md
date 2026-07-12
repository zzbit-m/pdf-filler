# app/services/ — AGENTS.md

## Non-obvious behavior
- `render_preview()` at 150 DPI produces 1240×1754 PNG for A4 — `zoom = dpi / 72`
- Two PyMuPDF APIs used: `insert_textbox()` when max_width set, plain `insert_text()` otherwise
- `pixel_to_point()` is called in the **router layer** (`save_template()` in template.py), not from any service
- `font_loader.py` searches system fonts as fallback but never logs the selected path
- Bundled Thai TTF at `app/fonts/tahoma.ttf` — `font_loader.py` searches bundled `app/fonts/` first with specific Thai TTF candidates, then falls back to system fonts
- fitz `insert_text()` y-pos doesn't round-trip through `get_text("words")` — text inserted at y=100 is extracted at y≈89 (≈11pt offset due to different font metric calculations). Tests must use approximate assertions
- `render_preview()` cache filename is `page_{page_number}.png` — does NOT include DPI. Two callers at different DPIs collide on the same cache file (last render wins). The thumbnail endpoint intentionally uses default 150 DPI to share cache with the preview endpoint
- `page.insert_text(fontfile=...)` does NOT embed the font in the PDF — it loads font for glyph metrics but the output references Helvetica/WinAnsiEncoding. Always call `page.insert_font(fontfile=path, fontname=X)` first to embed, then pass `fontname=X` to insert_text() without fontfile
- Embedding Tahoma inflates output PDF from ~17KB to ~970KB per file. Each output doc embeds the full TTF anew; font subsetting (not implemented) would reduce this
- Overlay receives content-space coordinates (already transformed by template router) — no rotation handling needed in `pdf_overlay.py`
- `template_manager.duplicate()` uses defensive dict comprehension `{k: v for k, v in src.items() if k not in {"id", "created_at"}}` — automatically forward-carries any future fields added to the template schema
- `overlay_fields()` renders `type == "text"` fields on EVERY page (not just their stored `page` value), while `type == "column"` fields render only on their assigned page. Text-field text_value is read directly from the field definition, not from Excel data
