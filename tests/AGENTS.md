# tests/ — AGENTS.md

## Patterns
- Sample PDF generated programmatically in `conftest.py` via `fitz` — no real PDF files bundled
- Sample Excel generated in `conftest.py` via `openpyxl` — no real Excel files bundled
- 7 test files (no test for `main.py` entrypoint)
- `font_loader.py` has only 1 test — most lightly tested service module
- Ruff E741 flags `l` as an ambiguous variable name — use `lab`/`lb`/`row` in list comprehensions instead
- `test_get_corrupt_file_returns_none` accesses `mgr._path(tid)` (private API) to overwrite a template file with bad JSON for corrupt-resilience testing
