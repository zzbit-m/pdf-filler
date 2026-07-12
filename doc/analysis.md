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
- [x] 4. Coordinate normalization — backend converts preview pixel clicks → PDF points (1/72"). Template stores only PDF-point coordinates, never pixels. Refactored to use PyMuPDF's `derotation_matrix` so all rotations are handled uniformly (no per-rotation if/else).
      → `app/services/pdf_preview.py:pixel_to_point()` converts pixel → point (`pixel * 72 / dpi`); called by `app/routers/template.py:save_template()` (L32-39 builds `page_derotation` dict from `doc[i].derotation_matrix`; L44-46 applies `fitz.Point(...) * derot` per field) before storing fields
- [x] 5. Bundle Thai TTF in project; `PdfOverlay` embeds the font into the output PDF and uses it for `insert_text()`. Verify Thai glyphs render with real names from Excel.
      → `app/fonts/tahoma.ttf` bundled (Tahoma supports Thai); `app/services/pdf_overlay.py:24-30` calls `page.insert_font(fontfile=path, fontname="FillCustom")` to **embed** Tahoma (Type0 CID with Identity-H), then `insert_text(fontname="FillCustom", ...)` at L60-61 — must use `insert_font` first, otherwise `fontfile` alone does not embed; `tests/test_pdf_overlay.py:test_thai_text_rendering` verifies Thai text overlay produces larger output file with content blocks
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
      → 72 tests collected, 72 passed (~5s). Guard chain: ruff ✅ mypy ✅ pytest ✅.

### Phase 2

- [x] 1. Frontend page navigation — prev/next buttons cycle `state.currentPage` and call `loadPreview()`; page indicator shows "Page N / total"
      → `app/static/app.js:5-6` (`currentPage`, `pageCount`), `:198` (`loadPreview(1)` on enter), `:202-207` (`loadPreview()` fetches `/preview/{pdf_id}/{page}`), `:209-225` (prev/next button handlers); `app/static/index.html:63-67` (nav UI)
- [x] 2. Fields can be positioned on different pages — drag-drop captures `state.currentPage` into field; same column can be on multiple pages; markers filtered by `f.page === state.currentPage`; removal is page-specific
      → `app/static/app.js:261-267` (drop stores `page: state.currentPage`), `:281` (`pageFields = state.placedFields.filter(f => f.page === state.currentPage)`), `:374-375` (`removeField(column, page)`), `:344` (marker shows `p{N}` badge)
- [x] 3. `TemplateField` model includes `page` (int, ge=1) — stored 0-indexed after conversion
      → `app/schemas/models.py:16-22`; `app/routers/template.py:46-59` converts `f.page - 1` and applies derotation per page
- [x] 4. Overlap detection checks same-page fields only — fields on different pages never trigger overlap warnings
      → `app/routers/template.py:63-75` (`if a["page"] == b["page"]`)
- [x] 5. `PdfOverlay` renders each field on its stored page — validates `page_num` is in range; silently skips out-of-range pages
      → `app/services/pdf_overlay.py:34-38` (`page = doc[page_num]` with bounds check); `tests/test_pdf_overlay.py:45-53` (`test_skip_out_of_range_page`)
- [x] 6. Per-page preview endpoints — preview and generated-output preview all accept 1-indexed page, convert to 0-indexed for fitz
      → `app/routers/preview.py:66-89` (preview), `fill.py:284-312` (generated preview)
- [x] 7. Tests cover multi-page field positioning — fields with `page` values in save requests and overlay
      → `tests/test_routers.py` (fields sent with `"page": N`); `tests/test_pdf_overlay.py` (page 0 for single-page, page 999 for out-of-range)

  **Minor gap (frontend-only):** Generated-output preview in Step 3 always sets `state.previewPageCount = 1` (`app.js:782,968`), so "Next Page" stays disabled even for multi-page output. Backend fully supports multi-page (`fill.py:301-308` accepts `page` parameter, calls `render_preview(pdf_path, zero_indexed)`). Fix: query the actual page count from the generated PDF via `pdf_preview.render_preview()` or a dedicated metadata endpoint.

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
- [x] 13. Guard chain passes — ruff, mypy, 112/112 pytest
      → ruff ✅, mypy ✅, `uv run pytest -x` 112 passed (~5s)

### Critical fixes (discovered during real fill runs)

These were not in any phase plan. Each was found when the user ran the actual fill on a real Thai PDF and saw unexpected output.

- [x] 1. **Font embedding** — `page.insert_text(fontfile=...)` does NOT embed the font in the output PDF. The PDF references Helvetica/WinAnsiEncoding, so character codes from Tahoma's internal mapping (0xB7) get written instead of the correct ASCII codes (e.g. "Mr." → 0xB7 0xB7 0xB7). Visible to the user as "no text" in any external PDF viewer, even though `get_text()` round-trips fine.
      → `app/services/pdf_overlay.py:24-30` calls `page.insert_font(fontfile=path, fontname="FillCustom")` to embed; `insert_text(..., fontname="FillCustom")` at L60-61 references the embedded font. Verified: output PDF has font `[(9, 'ttf', 'Type0', 'Tahoma Regular', 'FillCustom', 'Identity-H')]` and extracted text matches input. Tradeoff: each output PDF balloons from ~17KB to ~970KB (full TTF embedded).
- [x] 2. **Rotated-page coordinate conversion** — `save_template()` did `y = page_h - py` regardless of `page.rotation`, which is only correct for Rotate 0. On a Rotate 270 Thai government form (MediaBox 842×595, displayed as 595×842), the stored coordinates were in the wrong space and `insert_text()` placed text on the right edge rotated 90° instead of at the click position.
      → `app/routers/template.py:32-46` builds a `page_derotation` dict from `doc[i].derotation_matrix` per page, then for each field applies `fitz.Point(pixel_to_point(f.x), pixel_to_point(f.y)) * derot` — uniform matrix approach replaces the original per-rotation if/else. Verified by `tests/test_rotation.py:TestRotationConversion` (5 tests) which check the saved unrotated coords against `derotation_matrix` for all 4 rotations.
- [x] 3. **Generated-PDF preview** — user asked for a preview of the generated (filled) PDFs, not just the original template PDF.
      → `app/routers/fill.py:244-272` adds `GET /fill/{batch_id}/preview/{index}/{page}` rendering a specific filled output via `render_preview()` to `data/preview_cache/{batch_id}/`. Frontend `app/static/index.html:171-185` adds `#fill-preview` panel with file/page nav; `app/static/app.js:936-948` calls the endpoint after fill completes, caches-busted with `?t=Date.now()`.
- [x] 4. **Guard chain still passes** — ruff, mypy, pytest all pass
- [x] 5. **Text orientation on rotated pages** — after fix #2, the position was correct but the inserted text was rendered vertical/upside-down on rotated pages because the page's own rotation also rotated the inserted text. `pdf_overlay.py` now passes `rotate=page.rotation` to both `insert_text` and `insert_textbox` so the text is counter-rotated in the unrotated frame and lands horizontal in the visual frame.
      → `app/services/pdf_overlay.py:48` (`text_rotate = page.rotation`), applied at L53-69. Verified by `tests/test_pdf_overlay.py:100-135` (`test_text_horizontal_on_rotated_page`) which builds pages for all 4 rotations, inserts text, renders, and asserts the rendered text's Y-spread stays within ~2.5× font height (i.e., a single line, not a vertical column). Round-trip verified end-to-end on the user's actual TOG form PDF (Rot 270, mediabox 842×595): "นาย Phillip Dietz" appears horizontal at preview pixel (689, 630) — exactly the click position.
- [x] 6. **Guard chain still passes** — ruff, mypy, pytest all pass
