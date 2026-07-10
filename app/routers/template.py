from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas.models import (
    TemplateDuplicateRequest,
    TemplateListItem,
    TemplateRenameRequest,
    TemplateSaveRequest,
    TemplateSaveResponse,
)
from app.services.pdf_preview import pixel_to_point, render_preview
from app.services.template_manager import PDF_FILE_RE, TemplateManager

router = APIRouter(prefix="/template", tags=["template"])

TEMPLATES_DIR = Path("data/templates")
UPLOAD_DIR = Path("data/uploads")
PREVIEW_CACHE_DIR = Path("data/preview_cache")
manager = TemplateManager(TEMPLATES_DIR)


@router.post("", response_model=TemplateSaveResponse)
async def save_template(req: TemplateSaveRequest) -> TemplateSaveResponse:
    if not req.fields:
        raise HTTPException(400, detail="At least one field position is required")

    converted = []
    for f in req.fields:
        converted.append({
            "column": f.column,
            "page": f.page,
            "x": pixel_to_point(f.x),
            "y": pixel_to_point(f.y),
            "font_size": f.font_size,
            "max_width": f.max_width,
        })

    warnings: list[str] = []
    for i, a in enumerate(converted):
        for b in converted[i + 1:]:
            if a["page"] == b["page"]:
                ax: float = cast(float, a["x"])
                bx: float = cast(float, b["x"])
                dx = abs(ax - bx)
                ay: float = cast(float, a["y"])
                by: float = cast(float, b["y"])
                dy = abs(ay - by)
                if dx < 5 and dy < 5:
                    warnings.append(
                        f"Fields '{a['column']}' and '{b['column']}' overlap on page {a['page']}"
                    )

    template_id = manager.save(name=req.name, pdf_file=req.pdf_file, fields=converted)
    template = manager.get(template_id)
    assert template is not None

    return TemplateSaveResponse(
        id=template["id"],
        name=template["name"],
        pdf_file=template["pdf_file"],
        version=template["version"],
        field_count=len(converted),
        created_at=template["created_at"],
        warnings=warnings,
    )


@router.get("/list", response_model=list[TemplateListItem])
async def list_templates() -> list[TemplateListItem]:
    return [TemplateListItem(**t) for t in manager.list_all()]


@router.get("/{template_id}")
async def get_template(template_id: str) -> dict[str, Any]:
    template = manager.get(template_id)
    if template is None:
        raise HTTPException(404, detail="Template not found")
    return template


@router.delete("/{template_id}")
async def delete_template(template_id: str) -> dict[str, bool]:
    if not manager.delete(template_id):
        raise HTTPException(404, detail="Template not found")
    return {"ok": True}


@router.put("/{template_id}", response_model=TemplateListItem)
async def rename_template(template_id: str, req: TemplateRenameRequest) -> TemplateListItem:
    template = manager.get(template_id)
    if template is None:
        raise HTTPException(404, detail="Template not found")
    if not manager.rename(template_id, req.name):
        raise HTTPException(404, detail="Template not found")
    updated = manager.get(template_id)
    assert updated is not None
    return TemplateListItem(
        id=updated["id"],
        name=updated["name"],
        pdf_file=updated["pdf_file"],
        version=updated["version"],
        created_at=updated["created_at"],
        field_count=len(updated.get("fields", [])),
    )


@router.post("/{template_id}/duplicate", response_model=TemplateSaveResponse)
async def duplicate_template(
    template_id: str, req: TemplateDuplicateRequest
) -> TemplateSaveResponse:
    template = manager.duplicate(template_id, name=req.name)
    if template is None:
        raise HTTPException(404, detail="Template not found")
    return TemplateSaveResponse(
        id=template["id"],
        name=template["name"],
        pdf_file=template["pdf_file"],
        version=template["version"],
        field_count=len(template.get("fields", [])),
        created_at=template["created_at"],
    )


@router.get("/{template_id}/thumbnail")
async def thumbnail_template(template_id: str) -> FileResponse:
    template = manager.get(template_id)
    if template is None:
        raise HTTPException(404, detail="Template not found")

    pdf_file: str = template.get("pdf_file", "")
    if not PDF_FILE_RE.match(pdf_file):
        raise HTTPException(404, detail="Template PDF not found")

    pdf_path = UPLOAD_DIR / pdf_file
    if not pdf_path.exists():
        raise HTTPException(404, detail="Template PDF not found")

    page_cache_dir = PREVIEW_CACHE_DIR / pdf_file.replace(".pdf", "")
    page_cache_dir.mkdir(parents=True, exist_ok=True)
    result = render_preview(pdf_path, 0, cache_dir=page_cache_dir)
    cached_path = Path(result["image_path"])
    return FileResponse(str(cached_path), media_type="image/png")
