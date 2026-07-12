# app/ — AGENTS.md

## Design notes
- Overlay silently skips missing/empty columns (`overlay_fields()` in pdf_overlay.py) — no warning to caller
- Overlap detection threshold: <5pt on same page, heuristic check in `save_template()` (template.py)
- `font_loader.py` never logs which font was selected — silent system fallback makes debugging font issues harder
- Text fields (`type == "text"`) render on EVERY page of the output document, not just their stored `page` value. Column fields render only on their assigned page. This is by design: text fields typically hold static labels (e.g., "Draft") that should appear on every page.
