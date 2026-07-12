# PDF Filler

Drag Excel column names onto a flat PDF preview to set positions, then generate filled copies — one per data row.

## Install

```bash
git clone https://github.com/zzbit-m/pdf-filler.git
cd pdf-filler
uv venv
uv pip install -e ".[dev]"
```

## Run

Double-click **`start.bat`** — it installs dependencies automatically and opens `http://localhost:8000` in your browser.

Close the terminal window to stop the server.

## Use

**Step 1 — Upload**
- Upload an **Excel file** (`.xlsx`, header row at row 3) — detects columns and shows a preview
- Upload a **flat PDF template** (no form fields) — the page to fill

**Step 2 — Position**
- Drag column labels from the sidebar onto the PDF preview to place them
- Adjust font size and max-width per field
- Save as a template

**Step 3 — Generate**
- Pick a saved template, upload your data Excel, generate
- Download the result as a ZIP

## Commands

| Action | Command |
|--------|---------|
| lint | `uv run ruff check .` |
| typecheck | `uv run mypy .` |
| test | `uv run pytest -x` |
| serve | `uv run uvicorn app.main:app --reload` |

## How it works

Excel data is overlaid onto the PDF using PyMuPDF (`fitz`) text insertion at saved coordinates. The PDF is flat — no AcroForm fields, no annotation layer. Templates are stored as JSON files in `data/templates/`.
