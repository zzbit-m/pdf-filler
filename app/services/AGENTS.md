# app/services/ — AGENTS.md

## Non-obvious behavior
- `render_preview()` at 150 DPI produces 1240×1754 PNG for A4 — `zoom = dpi / 72`
- Two PyMuPDF APIs used: `insert_textbox()` when max_width set, plain `insert_text()` otherwise
- `pixel_to_point()` is called in the **router layer** (`template.py:30-31`), not from any service
- `font_loader.py` searches system fonts as fallback but never logs the selected path
- Bundled Thai TTF at `app/fonts/tahoma.ttf` — `font_loader.py` searches bundled `app/fonts/` first with specific Thai TTF candidates, then falls back to system fonts
- `_word_overlap()` splits on whitespace only — "Name-Surname" is one token, hyphens/underscores don't split. Substring boost is the only fallback for hyphenated matches
- `_combined_score()` is unbounded — `max(seq, overlap) + boost` can exceed 1.0 (e.g., exact match 1.0 + 0.15 boost = 1.15). Fine for relative sorting but misleading as "confidence" value
- fitz `insert_text()` y-pos doesn't round-trip through `get_text("words")` — text inserted at y=100 is extracted at y≈89 (≈11pt offset due to different font metric calculations). Tests must use approximate assertions
- `render_preview()` cache filename is `page_{page_number}.png` — does NOT include DPI. Two callers at different DPIs collide on the same cache file (last render wins). The thumbnail endpoint intentionally uses default 150 DPI to share cache with the preview endpoint
- `template_manager.duplicate()` uses defensive dict comprehension `{k: v for k, v in src.items() if k not in {"id", "created_at"}}` — automatically forward-carries any future fields added to the template schema
