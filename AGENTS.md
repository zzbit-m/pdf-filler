# pdf-filler — AGENTS.md

## Quick start

```bash
uv venv
uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload
```

## Commands

| Action | Command |
|--------|---------|
| lint | `uv run ruff check .` |
| typecheck | `uv run mypy .` |
| test (single) | `uv run pytest tests/<file>.py -x` |
| test (all) | `uv run pytest -x` |
| serve | `uv run uvicorn app.main:app --reload` |

## Project structure

- **app/** — FastAPI backend + static frontend
  - `app/main.py` — app entrypoint
  - `app/routers/` — route handlers (upload, template, fill)
  - `app/services/` — business logic (excel_reader, pdf_preview, pdf_overlay, font_loader, template_manager)
  - `app/schemas/models.py` — Pydantic models
  - `app/static/` — HTML/CSS/JS (plain, no framework)
- **data/** — runtime directories: uploads/, templates/, output/
- **tests/** — mirrors app/ structure, one file per module
- **doc/analysis.md** — architecture, Phase 1 checklist, future phases

## Key facts

- Frontend is **plain HTML/CSS/JS** served by FastAPI's StaticFiles — no SPA framework
- UI style: **classic 2010s admin panel** — flat, bordered tables, no rounded corners/glassmorphism
- No database — templates stored as JSON files in `data/templates/`
- PDFs are **flat** (no form fields) — PyMuPDF (fitz) renders previews and overlays text at coordinates
- Excel must be .xlsx — openpyxl handles it
- Generated PDFs land in `data/output/`
- Preview images cached in `data/preview_cache/`
- **No code comments** — let the code speak
- `fitz.open()` raises `fitz.FileDataError` for corrupted PDFs — `upload.py` now catches it and returns 400, don't just check `needs_pass`
- Fill batch state is in-memory (`fill_state` dict in `fill.py`) — lost on server restart
- `pdf_file` in template JSON stores `{pdf_id}.pdf` (with extension), matching how `upload.py` saves files
- Frontend page numbers are 1-indexed; `preview.py` converts `page - 1` for fitz 0-indexed API
- `BackgroundTasks` used in `fill.py` — overlay errors set `fill_state[batch_id].status="error"` with message (propagated to user), not silently swallowed
- Template JSON stores fields as raw dicts, not Pydantic serialization — no type validation on read
- Excel header row is hardcoded at row 3 (1-indexed) in `excel_reader.py`
- StaticFiles mounts at `/` with `html=True` — serves index.html on base URL; API routes mounted first so they take precedence
- Debugging output PDFs: searching raw bytes for ASCII strings fails for CID fonts (Identity-H encoding) — use `page.get_text()` or `doc.xref_stream()` instead

## Workflow

Follow the lifecycle in doc/analysis.md:
- Phase 1 items are concrete and verifiable
- After any build work, run `uv run ruff check . && uv run mypy . && uv run pytest -x`
- Use `/plan` before starting a new phase
- Use `/verify` to check Phase 1 items against real code
