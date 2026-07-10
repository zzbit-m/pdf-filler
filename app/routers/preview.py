from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.services.auto_position import extract_labels, suggest_positions
from app.services.pdf_preview import render_preview

router = APIRouter(prefix="/preview", tags=["preview"])

UPLOAD_DIR = Path("data/uploads")
CACHE_DIR = Path("data/preview_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/suggest/{pdf_id}/{page}")
async def get_suggestions(
    pdf_id: str, page: int, columns: list[str] = Query(...)
) -> dict[str, Any]:
    pdf_path = UPLOAD_DIR / f"{pdf_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, detail="PDF not found")

    zero_indexed = page - 1
    if zero_indexed < 0:
        raise HTTPException(400, detail="Page must be >= 1")

    if not columns:
        return {"suggestions": [], "hint": "No columns provided"}

    try:
        labels = extract_labels(str(pdf_path), zero_indexed)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    if not labels:
        return {
            "suggestions": [],
            "hint": "No text found on this page — the PDF may be scanned. Drag columns manually.",
        }

    suggestions = suggest_positions(labels, columns, threshold=0.7)
    return {"suggestions": suggestions, "hint": None}


@router.get("/{pdf_id}/{page}")
async def get_preview(pdf_id: str, page: int) -> FileResponse:
    pdf_path = UPLOAD_DIR / f"{pdf_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, detail="PDF not found")

    zero_indexed = page - 1
    if zero_indexed < 0:
        raise HTTPException(404, detail="Page out of range")

    page_cache_dir = CACHE_DIR / pdf_id
    page_cache_dir.mkdir(parents=True, exist_ok=True)
    cached_path = page_cache_dir / f"page_{zero_indexed}.png"

    if not cached_path.exists():
        try:
            result = render_preview(pdf_path, zero_indexed, cache_dir=page_cache_dir)
        except ValueError:
            raise HTTPException(404, detail="Page out of range")
        cached_path = Path(result["image_path"])

    return FileResponse(str(cached_path), media_type="image/png")
