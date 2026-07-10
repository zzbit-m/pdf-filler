# PDF Filler — Analysis

## Architecture

```
                     ┌─────────────────────────────┐
                     │      Web Browser (UI)        │
                     │  Upload · Drag columns ·     │
                     │  Generate · Download          │
                     └─────────────┬───────────────┘
                                   │ HTTP (FastAPI)
                     ┌─────────────▼───────────────┐
                     │    FastAPI Backend            │
                     │  /upload  /preview  /template │
                     │  /fill                        │
                     └─────────────┬───────────────┘
                                   │
          ┌────────────────────────┼─────────────────────────┐
          │                        │                         │
          ▼                        ▼                         ▼
   ┌──────────────┐       ┌──────────────┐         ┌──────────────┐
   │ ExcelReader   │       │  PdfPreview  │         │TemplateManager│
   │ (openpyxl)    │       │  (fitz)      │         │  (JSON files) │
   └──────────────┘       └──────┬───────┘         └──────┬───────┘
                                 │                        │
                                 ▼                        ▼
                         ┌──────────────┐        ┌──────────────┐
                         │ PdfOverlay   │        │   uploads/   │
                         │ (fitz)       │        │   templates/ │
                         └──────────────┘        │   output/    │
                                                 └──────────────┘
```

### Data flow (one generation run)

```
Excel (.xlsx)  ──►  Read column names + employee rows
                            │
Flat PDF        ──►  Render each page as image for preview
                            │
                            ▼
          User drags column labels onto PDF preview images
          → stores (column_name, page_number, x, y, font_size)
                            │
                Save as template (.json)
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
  For row 1: overlay text at         For row N: overlay text at
  saved coordinates on PDF           saved coordinates on PDF
              │                           │
              ▼                           ▼
        employee_1.pdf              employee_N.pdf
```

### Template data shape

Each template stores positions like this:

```
{
  "name": "New Employee Onboarding",
  "pdf_file": "some_uuid.pdf",
  "version": 1,
  "fields": [
    {
      "column": "Name-Surname",
      "page": 0,
      "x": 120.5,
      "y": 340.0,
      "font_size": 11
    },
    {
      "column": "Position",
      "page": 0,
      "x": 120.5,
      "y": 370.0,
      "font_size": 11
    }
  ]
}
```

### User screens (flow)

1. **Home / Upload** — Upload Excel + Upload PDF (or pick existing template to reuse)
2. **Position screen** — Splits into two areas:
   - Left sidebar: list of Excel column names (draggable)
   - Right: PDF preview (image per page) with page navigation
   - User drags column names onto the PDF preview → a label appears at drop position
   - User can click placed labels to delete or resize
   - "Save Template" button (name it)
3. **Generate screen** — Pick saved template, upload fresh Excel, click Generate
4. **Result screen** — Polls status, lists generated PDFs for download

## File structure

```
pdf-filler/
├── pyproject.toml
├── app/
│   ├── main.py                     # FastAPI app, static files mount
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── upload.py               # POST /upload/excel, /upload/pdf
│   │   ├── template.py             # POST/GET/DELETE /template
│   │   ├── preview.py              # GET /preview/{pdf_id}/{page}
│   │   └── fill.py                 # POST /fill, GET /fill/status, GET /fill/download
│   ├── services/
│   │   ├── __init__.py
│   │   ├── excel_reader.py         # read columns + rows from .xlsx
│   │   ├── pdf_preview.py          # render PDF page as image for drag UI
│   │   ├── pdf_overlay.py          # insert text at x,y coordinates on PDF
│   │   ├── auto_position.py        # extract labels + suggest positions (Phase 3)
│   │   └── template_manager.py     # CRUD for .json templates on disk
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── models.py               # Pydantic request/response models
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
├── data/
│   ├── uploads/                    # uploaded Excel & PDF files
│   ├── templates/                  # saved mapping templates (.json)
│   ├── preview_cache/              # cached PDF page images
│   └── output/                     # generated PDFs
├── tests/
│   ├── conftest.py                 # fixtures (sample Excel, sample PDF)
│   ├── test_excel_reader.py
│   ├── test_pdf_preview.py
│   ├── test_pdf_overlay.py
│   ├── test_auto_position.py
│   ├── test_font_loader.py
│   ├── test_fitz_smoke.py
│   ├── test_template_manager.py
│   └── test_routers.py
└── doc/
    └── analysis.md
```

## Decisions log

| Decision | Choice | Why |
|----------|--------|-----|
| Backend | Python + FastAPI | Good async, file handling, serves frontend easily |
| Frontend | Plain HTML/CSS/JS | Single-purpose tool, no framework overhead |
| PDF engine | **PyMuPDF (fitz)** | Renders PDF to image AND inserts text at coordinates — does both jobs |
| Excel library | openpyxl | Reads .xlsx without Excel installed, pure Python |
| Template storage | JSON on disk | Simple, portable, human-readable; no database needed |
| Deployment | Local web app | Zero setup for non-tech users; double-click to start, use in browser |
| Mapping UI | **Visual drag-and-drop** | PDFs are flat (no form fields). User must position text manually on a preview |

## Stability notes

| Likely to change | Likely stable |
|---|---|
| Drag-and-drop UX details (fine-tuning) | Template JSON schema (with `version` field) |
| Font size, text alignment, color options | Pipeline shape: Excel → Position → Overlay → Output |
| New PDF templates (different layouts) | PyMuPDF overlay interface |
| Improved suggestion accuracy (NLP/embedding-based) | Auto-position suggestions (fuzzy matching) |

## Testing strategy

- **Unit**: pytest for each service in isolation (ExcelReader, PdfPreview, PdfOverlay, TemplateManager)
- **Integration**: httpx.AsyncClient with FastAPI TestClient for endpoint tests with real files
- **Visual**: Manual test with real Thai PDF from `reference-files/` to verify overlay renders correctly
- **Structure**: Mirror `app/` under `tests/`, one file per module
- **CI command**: `uv run pytest -x`
- **Coverage target**: 80%+ on service layer, smoke tests on routes

## UI/UX direction

Classic 2010s admin panel style. Flat header, bordered tables, blue links, gray backgrounds. No rounded corners, glassmorphism, or over-designed elements. Functional and honest — looks hand-built by someone who cares about utility, not trends.

## Status checklist

### Phase 1 (detailed)

- [x] 1. `POST /upload/excel` — accepts .xlsx, returns column names + first 3 preview rows
      → `app/routers/upload.py:upload_excel`; validates `.xlsx` extension; calls `read_rows()` for columns + data; slices `rows[:3]` for preview
- [x] 2. `POST /upload/pdf` — accepts PDF (any kind), stores file, returns PDF id + page count
      → `app/routers/upload.py:upload_pdf`; saves to `data/uploads/{uuid}.pdf`; checks `doc.needs_pass` for encrypted; rejects 0-page PDFs
- [x] 3. `GET /preview/{pdf_id}/{page}` — renders a PDF page as PNG at fixed DPI for the drag UI
      → `app/routers/preview.py:get_preview`; uses `render_preview()` at 150 DPI; caches to `data/preview_cache/`; returns `image/png`
- [x] 4. Coordinate normalization — backend converts preview pixel clicks → PDF points (1/72"). Template stores only PDF-point coordinates, never pixels.
      → `app/services/pdf_preview.py:pixel_to_point()` converts pixel → point (`pixel * 72 / dpi`); called by `app/routers/template.py:save_template()` before storing fields
- [x] 5. Bundle Thai TTF in project; `PdfOverlay` uses `fitz.Font(fontfile=...)` with the bundled font for `insert_text()`. Verify Thai glyphs render with real names from Excel.
      → `app/fonts/tahoma.ttf` bundled (Tahoma supports Thai); added to `font_loader._THAI_CANDIDATES`; `tests/test_pdf_overlay.py:test_thai_text_rendering` verifies Thai text overlay produces larger output file with content blocks
- [x] 6. Frontend — **upload screen**: upload Excel + upload PDF; sidebar shows detected columns
      → `app/static/index.html` step-1 section; `app.js` handles upload via FormData + shows columns in tag-list + preview table
- [x] 7. Frontend — **position screen**: PDF preview (page navigable) + draggable column names from sidebar
      → `app/static/index.html` step-2; `app.js` enterStep2() populates #available-columns with draggable tags; loadPreview() renders PDF page
- [x] 8. Frontend — drop column label onto preview creates a positioned marker; marker shows column name
      → `app.js` drag-and-drop event handlers on #preview-wrapper; drop event calculates pixel position via naturalWidth/displayed ratio
- [x] 9. Frontend — click placed marker to delete it, resize font (clamped 6–36), or set max-width with truncation
      → `app.js` placed-field list with number input (min=6, max=36 clamped), text input for max_width, ✕ button to remove
- [x] 10. `POST /template` — saves field positions as JSON: `{column, page, x, y, font_size, max_width}`. Rejects if no fields placed. Warns if any two positions overlap (<5pt apart).
      → `app/routers/template.py:save_template`; `if not req.fields` → 400; nested loop checks `dx < 5 and dy < 5` on same page → warning returned in response
- [x] 11. `GET /template/list` — returns list of saved templates
      → `app/routers/template.py:list_templates`; calls `manager.list_all()`; returns `list[TemplateListItem]`
- [x] 12. `GET /template/{id}` — loads a saved template with all positions
      → `app/routers/template.py:get_template`; returns full template dict including `fields`; 404 if not found
- [x] 13. `DELETE /template/{id}` — deletes a saved template
      → `app/routers/template.py:delete_template`; returns `{"ok": True}` or 404
- [x] 14. `POST /fill` — accepts template ID + Excel file, returns batch ID (async); warns if any column in template not found in uploaded Excel
      → `app/routers/fill.py:start_fill`; uses `BackgroundTasks` for async processing; computes `template_columns - excel_columns` and returns warnings
- [x] 15. `GET /fill/{batch_id}/status` — progress polling (completed / total)
      → `app/routers/fill.py:fill_status`; returns `FillStatusResponse` from in-memory `fill_state` dict; 404 if batch unknown
- [x] 16. `GET /fill/{batch_id}/download` — zip download of all generated PDFs
      → `app/routers/fill.py:fill_download`; checks `status == "completed"`; uses `shutil.make_archive`; returns zip `FileResponse`
- [x] 17. Frontend — **generate screen**: pick template, upload new Excel, click Generate, poll + download
      → `app/static/index.html` step-3; `app.js` enterStep3() loads template list, startFill() POSTs file, startPolling() GETs status every 1s, shows download link on completion
- [x] 18. Error handling — wrong file type rejection, empty Excel, PDF that can't be rendered, empty cell values → skip overlay (no text placed), encrypted/read-only PDF rejection, corrupted PDF → 400, overlay errors propagated to user
      → wrong file type ✅ (`upload.py` extension checks); empty Excel ✅ (`upload.py:24-25`); encrypted PDF ✅ (`upload.py:40-42`); empty cell skip ✅ (`pdf_overlay.py:24`); corrupted PDF ✅ (`upload.py:39` catches `fitz.FileDataError` → 400); overlay errors ✅ (`fill.py:40-41` sets `fill_state[batch_id].status="error"` with message). Tested at `test_routers.py:test_corrupted_pdf` and `test_fill_overlay_error`.
- [x] 19. Frontend uses classic 2010s styling (flat, bordered tables, simple palette)
      → `app/static/style.css` — flat design, bordered tables with alternating rows, blue header (#4A90D9), flat buttons with hover states, no rounded corners or glassmorphism
- [x] 20. `uv run pytest -x` passes for all tests
      → 49 tests collected, 49 passed (1.78s). Guard chain: ruff ✅ mypy ✅ pytest ✅

### Phase 2

Multi-page support — position fields across different pages of the PDF

### Phase 3

- [x] 1. `extract_labels()` in `app/services/auto_position.py` — reads text from a PDF page via fitz `get_text("words")`, groups words into lines by block+line number, filters out empty/long strings
      → `app/services/auto_position.py:8-51`; groups by `(block_no, line_no)`, joins words with space, skips text >100 chars
- [x] 2. `suggest_positions()` with fuzzy scoring — matches Excel column names to extracted PDF labels using combined `SequenceMatcher` ratio + word overlap + substring boost; returns suggested (x, y, confidence) coordinates right of the matched label
      → `app/services/auto_position.py:54-105`; `_combined_score()` at L70-75 uses `max(seq, overlap) + boost`; coords at L97-101: `x = label["x1"] + 8`, `y = label["y0"]`; threshold default 0.7
- [x] 3. `GET /preview/suggest/{pdf_id}/{page}?columns=...` — API endpoint returning suggestions for a given PDF page; accepts columns as repeated query params
      → `app/routers/preview.py:17-44`; converts 1-indexed page to 0-indexed; returns `{"suggestions": [...], "hint": ...}`; 404 on missing PDF, 400 on bad page
- [x] 4. Frontend — suggestion checklist in sidebar: fetches suggestions on page load/page change, renders with confidence badges (high≥90%, mid≥70%, low<70%), checkboxes per suggestion
      → `app/static/app.js:316-364` (`fetchSuggestions` at L316, `renderSuggestions` at L337, confidence badge classes at L350-355); called at L170, L185, L194 on step2 enter and page change
- [x] 5. Frontend — "Apply Selected" button places checked suggestions as markers on the preview; suggestion markers render as dashed green border `.marker-suggestion`; duplicates and already-placed columns are skipped
      → `app/static/app.js:366-390` (`applySuggestions` at L366); `app.js:249-260` renders `.marker-suggestion` divs; `style.css:50` `.marker-suggestion` dashed green border
- [x] 6. Tests — 21 tests covering label extraction, scoring functions, and suggestion logic in isolation
      → `tests/test_auto_position.py` (21 tests in 3 classes: `TestExtractLabels`, `TestScoring`, `TestSuggestPositions`); `uv run pytest -x` passes all 70 tests

### Phase 4

- [x] 1. `template_manager.rename()` — renames a template; loads JSON, updates `name`, saves back. Returns `True`/`False`.
      → `app/services/template_manager.py:61-69`; delegates to `get()` to load + validate
- [x] 2. `template_manager.duplicate()` — creates a deep copy with new UUID; default name `"{original} (Copy)"`; defensive field copy excludes `id`/`created_at`, includes all other keys.
      → `app/services/template_manager.py:71-84`; `{k: v for k, v in src.items() if k not in {"id", "created_at"}}`
- [x] 3. Crash resilience — `list_all()` skips corrupt JSON files (wraps `json.loads()` in try/except `JSONDecodeError`+`OSError`); `get()` returns `None` on corrupt. `created_at` uses `.get("created_at", "")` for backward compat.
      → `app/services/template_manager.py:37-40` (list_all), `55-59` (get), `46` (created_at fallback)
- [x] 4. `PDF_FILE_RE` regex — `^[0-9a-f-]+\.pdf$` validates template `pdf_file` is UUID format before constructing file paths (mitigates path traversal).
      → `app/services/template_manager.py:8`; used by thumbnail endpoint at `template.py:134`
- [x] 5. `PUT /template/{id}` rename route — accepts `{name}` body with Pydantic `min_length=1, max_length=200`; returns updated `TemplateListItem`.
      → `app/routers/template.py:91-107`; `TemplateRenameRequest` at `models.py:49-50`
- [x] 6. `POST /template/{id}/duplicate` route — accepts optional `{name?}` body; returns new `TemplateSaveResponse` with new UUID; 404 if source not found.
      → `app/routers/template.py:110-124`; `TemplateDuplicateRequest` at `models.py:53-54`
- [x] 7. `GET /template/{id}/thumbnail` — serves first page of template's PDF as PNG via `render_preview()` at 150 DPI; validates pdf_file UUID pattern; 404 if template, PDF, or pattern mismatch.
      → `app/routers/template.py:127-145`; delegates to `render_preview(pdf_path, 0)`; caches at `preview_cache/{pdf_id}/page_0.png`
- [x] 8. Frontend — template card grid replaces `<select>`; each card shows thumbnail (lazy-loaded, onerror fallback), name, field count, Rename/Copy/Del buttons.
      → `app/static/index.html:90` (`#template-grid`); `app.js:454-507` (`renderTemplateGrid()`); `style.css:70-78` (`.template-grid`, `.template-card`, `.template-thumb`, `.template-card-name`, `.template-card-meta`, `.template-card-actions`)
- [x] 9. Frontend — card selection via click/Enter/Space; keyboard accessible (`role="button"`, `tabindex="0"`, `keydown` handler).
      → `app.js:464` (card HTML), `481-487` (keydown), `509-515` (`selectTemplate`)
- [x] 10. Frontend — rename via `window.prompt()` → `PUT /template/{id}`; duplicate via `POST /template/{id}/duplicate`; delete via `window.confirm()` → `DELETE /template/{id}` with state cleanup.
      → `app.js:517-525` (`renameTemplate`), `528-534` (`duplicateTemplate`), `537-549` (`deleteTemplate` — nulls `state.templateId` at L542)
- [x] 11. Tests — 7 new service tests: rename ×2, duplicate ×3, corrupt resilience ×2
      → `tests/test_template_manager.py:49-99` (`test_rename_existing`, `test_rename_nonexistent`, `test_duplicate_existing`, `test_duplicate_nonexistent`, `test_duplicate_custom_name`, `test_list_all_skips_corrupt_file`, `test_get_corrupt_file_returns_none`)
- [x] 12. Tests — 7 new integration tests: rename ×2, duplicate ×2, thumbnail ×3
      → `tests/test_routers.py:201-272` (`test_rename_template`, `test_rename_template_404`, `test_duplicate_template`, `test_duplicate_template_404`, `test_thumbnail`, `test_thumbnail_missing_pdf`, `test_thumbnail_invalid_pdf_file`)
- [x] 13. Guard chain passes — ruff, mypy, 84/84 pytest
      → ruff ✅, mypy ✅, `uv run pytest -x` 84 passed (4.12s)

### Phase 5

Batch multi-PDF templates (one Excel → many different PDF types)

- [x] 1. `excel_reader.read_unique_values()` — returns unique non-empty trimmed values from a named column in an Excel file
      → `app/services/excel_reader.py:64-84`; finds column by name in header row, collects unique stripped values from data rows, returns sorted list
- [x] 2. `WorkflowManager` — CRUD for workflow JSON files; mirrors `TemplateManager` pattern with `save()`, `list_all()`, `get()`, `rename()`, `delete()` and crash resilience (skips corrupt JSON in list, returns None for corrupt get)
      → `app/services/workflow_manager.py` (71 lines); stored in `data/workflows/` as UUID-named JSON files
- [x] 3. `ExcelUploadResponse.excel_id` — upload endpoint now returns the saved Excel file's UUID for per-file operations
      → `app/schemas/models.py:4-7`, `app/routers/upload.py:23-30`; `excel_id: str = ""` (default for backward compat); `upload_excel` captures UUID before constructing filename
- [x] 4. `GET /upload/{excel_id}/unique/{column}` — returns unique values from a column; validates `excel_id` with UUID regex before path construction
      → `app/routers/upload.py:33-41`; `EXCEL_ID_RE` re.compile at line 16; 400 on invalid ID, 404 on missing file
- [x] 5. `POST /workflow` — create workflow from `{name, routing_column, routes}`; rejects duplicate route values with 400
      → `app/routers/workflow.py:23-45`; `seen` set at line 25 validates uniqueness; `WorkflowSaveRequest` with `RouteEntry` in `models.py:72-80`
- [x] 6. `GET /workflow/list` — returns `WorkflowListItem` list with `route_count`
      → `app/routers/workflow.py:48-50`; `workflow_mgr.list_all()` → `WorkflowListItem`
- [x] 7. `GET /workflow/{id}` — returns full workflow with expanded template names (including "(deleted)" for missing templates)
      → `app/routers/workflow.py:53-68`; calls `template_mgr.get()` per route to expand names
- [x] 8. `PUT /workflow/{id}` — rename workflow; reuses `TemplateRenameRequest` schema
      → `app/routers/workflow.py:71-88`; validates existence, renames, returns updated `WorkflowListItem`
- [x] 9. `DELETE /workflow/{id}` — delete workflow
      → `app/routers/workflow.py:91-95`; returns `{"ok": True}` or 404
- [x] 10. `POST /fill/workflow?workflow_id=X` — start workflow batch fill
      → `app/routers/fill.py:151-190`; validates workflow exists (L158), has routes (L161), routing column present in Excel (L173); warns about unmapped values (L176-184); launches `_run_workflow_batch` background task (L188)
- [x] 11. `_run_workflow_batch()` — per-row routing lookup + overlay; builds `routes` dict from workflow routes; skips empty routing values, unmapped values, and deleted templates with per-row warnings in `fill_state`; uses `_sanitize_filename()` for output filenames; error handling sets `status="error"` with accumulated warnings
      → `app/routers/fill.py:63-117`; three skip conditions at L77-96, overlay at L103, warnings accumulated and included in every state update
- [x] 12. `_sanitize_filename()` — strips non-word characters via `re.sub(r"[^\w\-]", "_", value)[:100]`
      → `app/routers/fill.py:30-31`
- [x] 13. `FillStatusResponse.warnings` — batch-level warnings (skipped rows, unmapped values) surfaced through status endpoint for frontend display
      → `app/schemas/models.py:69`; `fill_status` in `fill.py:204` returns `state.get("warnings", [])`
- [x] 14. Frontend — two-tab layout in Step 3: "Single Template" / "Workflow Batch" with `switchStep3Tab()` toggling between them; shared progress/download/error section below both tabs
      → `app/static/index.html:87-151` (`.step3-tabs` + `#tab-single` + `#tab-workflow` + shared `#fill-progress`/`#fill-done`/`#fill-error` at L143-150); `app.js:439-445` (`switchStep3Tab`), `main.py:5,12` registers `workflow.router`
- [x] 15. Frontend — workflow builder: name input + Excel upload → column picker → value-to-template mapping table → save; `resetWorkflowBuilder()` for cleanup
      → `app/static/index.html:114-137`; `app.js:757-863` (toggle panel at L757, `resetWorkflowBuilder` at L762, Excel upload handler at L773, routing column change at L797, `renderRoutingValues` at L814, save handler at L833)
- [x] 16. Frontend — workflow card grid (gear icon, name, route_count, routing_column, Rename/Del buttons) with click/Enter/Space selection and action delegation
      → `app.js:666-755` (`loadWorkflows` at L666, `renderWorkflowGrid` at L676, `selectWorkflow` at L724, `renameWorkflow` at L732, `deleteWorkflow` at L743)
- [x] 17. Frontend — workflow fill: select workflow → upload data Excel → Generate → same `startPolling()` cycle with download link; batch warnings displayed on completion
      → `app.js:880-902` (workflow fill start); poll function at `636-647` shows `workflow-fill-warnings` on completion
- [x] 18. Frontend — workflow builder template dropdowns use cached `state.templates` from `loadTemplates()`
      → `app.js:474` (`state.templates = list`); `app.js:824` (`state.templates.forEach`)
- [x] 19. Service tests — 10 `WorkflowManager` tests: save/get, list, empty list, nonexistent get, delete existing/nonexistent, rename existing/nonexistent, corrupt file skip in list, corrupt get returns None
      → `tests/test_workflow_manager.py` (76 lines, class `TestWorkflowManager`); mirrors `test_template_manager.py` patterns
- [x] 20. Integration tests — 13 workflow tests: create, duplicate values rejection, empty routes rejection, list, get with expanded names, rename, delete, get 404, workflow fill routing (2 PDFs × 2 templates × 2 routes), missing routing column 400, workflow 404, no routes 400, deleted template graceful skip with warnings
      → `tests/test_routers.py:393-674` (class `TestWorkflow`); reuses `_create_pdf()` and `_create_excel()` helpers
- [x] 21. `read_unique_values` tests — column found, column not found
      → `tests/test_excel_reader.py:60-67`
- [x] 22. Guard chain passes — ruff, mypy, 109/109 pytest
      → ruff ✅, mypy ✅, `uv run pytest -x` 109 passed (verified at time of Phase 5 completion)
