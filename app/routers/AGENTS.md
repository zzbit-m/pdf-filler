# app/routers/ — AGENTS.md

## Gotchas
- `upload_pdf()` catches `fitz.FileDataError` from corrupted PDFs and returns HTTP 400
- `upload.py` deletes uploaded file on rejection (encrypted, 0-page, corrupted) — clean state but destructive on validation fail
- `_run_batch()` in fill.py sets `fill_state[batch_id].status="error"` with message on overlay failure — errors propagate to user via status endpoint
- Template router owns coordinate math (`pixel_to_point` call), not the service layer
- Preview router converts 1-indexed page URL to 0-indexed (`page - 1`) for fitz — frontend always sends 1-indexed pages
- Template save converts display (pixel) coordinates to content (point) coordinates — for rotated pages (Rotate 90/180/270), the transformation must swap x/y and adjust for media box dimensions, not just flip y-axis
