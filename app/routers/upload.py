import re
import uuid
from pathlib import Path

import fitz
from fastapi import APIRouter, HTTPException, UploadFile

from app.config import DATA_BASE
from app.schemas.models import ExcelUploadResponse, PdfUploadResponse
from app.services.excel_reader import read_rows, read_unique_values

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = DATA_BASE / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

EXCEL_ID_RE = re.compile(r"^[0-9a-f-]+$")

ALLOWED_EXCEL = {".xlsx", ".xlsm"}


@router.post("/excel", response_model=ExcelUploadResponse)
async def upload_excel(file: UploadFile) -> ExcelUploadResponse:
    if not file.filename:
        raise HTTPException(400, detail="No filename provided")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXCEL:
        raise HTTPException(400, detail=f"Unsupported file type '{ext}'. Use .xlsx or .xlsm")
    excel_id = str(uuid.uuid4())
    filepath = UPLOAD_DIR / f"{excel_id}.xlsx"
    content = await file.read()
    filepath.write_bytes(content)
    try:
        columns, rows = read_rows(filepath)
    except Exception:
        filepath.unlink(missing_ok=True)
        raise HTTPException(
            400,
            detail="Cannot read this Excel file. Save it as .xlsx and try again.",
        )
    if not columns:
        raise HTTPException(400, detail="Excel file has no columns in row 3")
    return ExcelUploadResponse(columns=columns, preview_rows=rows[:3], excel_id=excel_id)


@router.get("/{excel_id}/unique/{column}")
async def get_unique_values(excel_id: str, column: str) -> dict[str, list[str]]:
    if not EXCEL_ID_RE.match(excel_id):
        raise HTTPException(400, detail="Invalid excel ID")
    filepath = UPLOAD_DIR / f"{excel_id}.xlsx"
    if not filepath.exists():
        raise HTTPException(404, detail="Excel file not found")
    values = read_unique_values(filepath, column)
    return {"values": values}


@router.post("/pdf", response_model=PdfUploadResponse)
async def upload_pdf(file: UploadFile) -> PdfUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="Only PDF files are accepted")
    pdf_id = str(uuid.uuid4())
    filepath = UPLOAD_DIR / f"{pdf_id}.pdf"
    content = await file.read()
    filepath.write_bytes(content)

    try:
        doc = fitz.open(filepath)
    except fitz.FileDataError:
        raise HTTPException(400, detail="Invalid or corrupted PDF file")

    try:
        if doc.needs_pass:
            filepath.unlink()
            raise HTTPException(400, detail="Encrypted PDF — please provide a decrypted copy")
        page_count = doc.page_count
        if page_count == 0:
            filepath.unlink()
            raise HTTPException(400, detail="PDF has no pages")
    finally:
        doc.close()

    return PdfUploadResponse(pdf_id=pdf_id, page_count=page_count, filename=file.filename)
