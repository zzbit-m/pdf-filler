import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import DATA_BASE
from app.services.pdf_preview import render_preview

router = APIRouter(prefix="/preview", tags=["preview"])

PDF_ID_RE = re.compile(r"^[0-9a-f-]+$")
UPLOAD_DIR = DATA_BASE / "uploads"
CACHE_DIR = DATA_BASE / "preview_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/{pdf_id}/{page}")
async def get_preview(pdf_id: str, page: int) -> FileResponse:
    if not PDF_ID_RE.match(pdf_id):
        raise HTTPException(400, detail="Invalid PDF ID")
    pdf_path = UPLOAD_DIR / f"{pdf_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, detail="PDF not found")

    zero_indexed = page - 1
    if zero_indexed < 0:
        raise HTTPException(400, detail="Page must be >= 1")

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
