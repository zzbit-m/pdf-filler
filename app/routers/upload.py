import uuid
from pathlib import Path

import fitz
from fastapi import APIRouter, HTTPException, UploadFile

from app.config import DATA_BASE
from app.schemas.models import ExcelUploadResponse, PdfUploadResponse
from app.services.excel_reader import read_rows
from app.services.pdf_preview import render_preview

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = DATA_BASE / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = DATA_BASE / "preview_cache"

ALLOWED_EXCEL = {".xlsx", ".xlsm"}
MAX_UPLOAD_SIZE = 100 * 1024 * 1024


@router.post("/excel", response_model=ExcelUploadResponse)
async def upload_excel(file: UploadFile) -> ExcelUploadResponse:
    if not file.filename:
        raise HTTPException(400, detail="No filename provided")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXCEL:
        raise HTTPException(400, detail=f"Unsupported file type '{ext}'. Use .xlsx or .xlsm")
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, detail="File too large (max 100MB)")
    excel_id = str(uuid.uuid4())
    filepath = UPLOAD_DIR / f"{excel_id}.xlsx"
    filepath.write_bytes(content)
    try:
        columns, rows = read_rows(filepath)
    except Exception:
        import logging
        logging.getLogger("pdf_filler").warning("Excel read failed", exc_info=True)
        filepath.unlink(missing_ok=True)
        raise HTTPException(
            400,
            detail="Cannot read this Excel file. Save it as .xlsx and try again.",
        )
    if not columns:
        raise HTTPException(400, detail="Excel file has no columns in row 3")
    return ExcelUploadResponse(columns=columns, preview_rows=rows[:3], excel_id=excel_id)


@router.post("/pdf", response_model=PdfUploadResponse)
async def upload_pdf(file: UploadFile) -> PdfUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="Only PDF files are accepted")
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, detail="File too large (max 100MB)")
    pdf_id = str(uuid.uuid4())
    filepath = UPLOAD_DIR / f"{pdf_id}.pdf"

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except fitz.FileDataError:
        raise HTTPException(400, detail="Invalid or corrupted PDF file")

    try:
        if doc.needs_pass:
            raise HTTPException(400, detail="Encrypted PDF — please provide a decrypted copy")
        page_count = doc.page_count
        if page_count == 0:
            raise HTTPException(400, detail="PDF has no pages")
    finally:
        doc.close()

    filepath.write_bytes(content)

    try:
        page_cache_dir = CACHE_DIR / pdf_id
        render_preview(filepath, 0, cache_dir=page_cache_dir)
    except Exception:
        import logging
        logging.getLogger("pdf_filler").warning(
            "Preview render failed for PDF %s", pdf_id, exc_info=True
        )

    return PdfUploadResponse(pdf_id=pdf_id, page_count=page_count, filename=file.filename)
