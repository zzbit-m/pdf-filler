# app/ — AGENTS.md

## Design notes
- Overlay silently skips missing/empty columns (`pdf_overlay.py:24`) — no warning to caller
- Overlap detection threshold: <5pt on same page, heuristic check in `template.py:37-49`
- `font_loader.py` never logs which font was selected — silent system fallback makes debugging font issues harder
