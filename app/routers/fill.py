import logging
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import DATA_BASE
from app.schemas.models import AdjustFieldRequest, FillStartResponse, FillStatusResponse
from app.services.excel_reader import read_rows
from app.services.pdf_overlay import overlay_fields
from app.services.pdf_preview import pixel_to_point, point_to_pixel, render_preview
from app.services.template_manager import PDF_FILE_RE, TemplateManager

router = APIRouter(prefix="/fill", tags=["fill"])

logger = logging.getLogger("pdf_filler")

UPLOAD_DIR = DATA_BASE / "uploads"
TEMPLATES_DIR = DATA_BASE / "templates"
OUTPUT_DIR = DATA_BASE / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_PREVIEW_CACHE = DATA_BASE / "preview_cache" / "generated"

ALLOWED_EXCEL = {".xlsx", ".xlsm"}
MAX_FILL_ROWS = 10_000

manager = TemplateManager(TEMPLATES_DIR)

fill_state: dict[str, dict[str, Any]] = {}
_fill_state_lock = threading.Lock()


def _set_fill_state(batch_id: str, state: dict[str, Any]) -> None:
    with _fill_state_lock:
        fill_state[batch_id] = state


def _get_fill_state(batch_id: str) -> dict[str, Any] | None:
    with _fill_state_lock:
        return fill_state.get(batch_id)


def _sanitize_filename(value: str) -> str:
    return re.sub(r"[^\w\-]", "_", value)[:100]


def _run_batch(batch_id: str, template: dict[str, Any], excel_path: Path) -> None:
    try:
        _, rows = read_rows(excel_path)
        if len(rows) > MAX_FILL_ROWS:
            _set_fill_state(
                batch_id,
                {"status": "error", "completed": 0, "total": 0,
                 "error": f"Too many rows (max {MAX_FILL_ROWS})"},
            )
            return
        fields = template.get("fields", [])
        if not fields:
            _set_fill_state(
                batch_id,
                {"status": "error", "completed": 0, "total": 0,
                 "error": "Template has no fields"},
            )
            return
        pdf_file = template.get("pdf_file", "")
        if not pdf_file or not PDF_FILE_RE.match(pdf_file):
            _set_fill_state(
                batch_id,
                {"status": "error", "completed": 0, "total": 0,
                 "error": "Template references an invalid PDF file"},
            )
            return
        pdf_path = UPLOAD_DIR / pdf_file
        if not pdf_path.exists():
            _set_fill_state(
                batch_id,
                {"status": "error", "completed": 0, "total": 0,
                 "error": "Template PDF file not found on disk"},
            )
            return

        batch_output = OUTPUT_DIR / batch_id
        batch_output.mkdir(parents=True, exist_ok=True)

        total = len(rows)
        files: list[str] = []
        for i, row in enumerate(rows):
            try:
                filename = f"employee_{i + 1}.pdf"
                output_path = batch_output / filename
                overlay_fields(pdf_path, fields, row, output_path)
                files.append(filename)
            except Exception:
                logger.exception("Overlay failed for row %d of batch %s", i + 1, batch_id)
                _set_fill_state(batch_id, {
                    "status": "error", "total": total, "completed": i,
                    "error": "An internal error occurred during PDF generation",
                })
                return
            _set_fill_state(batch_id, {"status": "processing", "total": total, "completed": i + 1})

        existing = _get_fill_state(batch_id)
        prior_warnings: list[str] = []
        if existing is not None:
            prior_warnings = existing.get("warnings", [])

        zip_path = OUTPUT_DIR / f"{batch_id}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(batch_output))

        _set_fill_state(batch_id, {
            "status": "completed",
            "total": total,
            "completed": total,
            "output_dir": str(batch_output),
            "files": files,
            "warnings": prior_warnings,
            "template_id": template.get("id"),
            "excel_path": str(excel_path),
            "zip_path": str(zip_path),
            "adjustments": {},
        })
    except Exception:
        logger.exception("Batch %s failed", batch_id)
        _set_fill_state(
            batch_id,
            {"status": "error", "completed": 0, "total": 0,
             "error": "An internal error occurred during PDF generation"},
        )


@router.post("", response_model=FillStartResponse)
async def start_fill(
    template_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
) -> FillStartResponse:
    template = manager.get(template_id)
    if template is None:
        raise HTTPException(404, detail="Template not found")

    if not file.filename or Path(file.filename).suffix.lower() not in ALLOWED_EXCEL:
        raise HTTPException(400, detail="Only .xlsx and .xlsm files are accepted")

    excel_path = UPLOAD_DIR / f"{uuid.uuid4()}.xlsx"
    content = await file.read()
    excel_path.write_bytes(content)

    excel_columns, _ = read_rows(excel_path)
    template_columns = {f["column"] for f in template["fields"] if f.get("type") != "text"}
    missing = template_columns - set(excel_columns)
    warnings: list[str] = []
    if missing:
        warnings.append(f"Columns not found in Excel: {', '.join(sorted(missing))}")

    batch_id = str(uuid.uuid4())
    _set_fill_state(
        batch_id, {"status": "pending", "total": 0, "completed": 0, "warnings": warnings}
    )
    background_tasks.add_task(_run_batch, batch_id, template, excel_path)

    return FillStartResponse(batch_id=batch_id, warnings=warnings)


@router.get("/{batch_id}/status", response_model=FillStatusResponse)
async def fill_status(batch_id: str) -> FillStatusResponse:
    state = _get_fill_state(batch_id)
    if state is None:
        raise HTTPException(404, detail="Batch not found")
    return FillStatusResponse(
        batch_id=batch_id,
        status=state["status"],
        completed=state["completed"],
        total=state["total"],
        error=state.get("error"),
        warnings=state.get("warnings", []),
        files=state.get("files", []),
    )


@router.get("/{batch_id}/download")
async def fill_download(batch_id: str) -> FileResponse:
    state = _get_fill_state(batch_id)
    if state is None:
        raise HTTPException(404, detail="Batch not found")
    if state["status"] != "completed":
        raise HTTPException(400, detail="Batch not yet completed")

    output_dir = Path(state["output_dir"])
    zip_path = Path(state.get("zip_path", ""))
    if not zip_path.exists():
        zip_path = OUTPUT_DIR / f"{batch_id}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(output_dir))

    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename=f"filled_{batch_id}.zip",
    )


@router.get("/{batch_id}/preview/{index}/{page}")
async def generated_preview(batch_id: str, index: int, page: int) -> FileResponse:
    state = _get_fill_state(batch_id)
    if state is None:
        raise HTTPException(404, detail="Batch not found")
    if state["status"] != "completed":
        raise HTTPException(400, detail="Batch not yet completed")

    files: list[str] = state.get("files", [])
    if index < 1 or index > len(files):
        raise HTTPException(404, detail="File index out of range")

    output_dir = Path(state["output_dir"])
    pdf_path = output_dir / files[index - 1]
    if not pdf_path.exists():
        raise HTTPException(404, detail="Generated PDF not found")

    zero_indexed = page - 1
    if zero_indexed < 0:
        raise HTTPException(400, detail="Page must be >= 1")

    cache_dir = GENERATED_PREVIEW_CACHE / batch_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = render_preview(pdf_path, zero_indexed, cache_dir=cache_dir)
    except ValueError:
        raise HTTPException(404, detail="Page out of range")

    return FileResponse(str(Path(result["image_path"])), media_type="image/png")


@router.get("/{batch_id}/fields/{index}/{page}")
async def fill_field_positions(batch_id: str, index: int, page: int) -> list[dict[str, Any]]:
    state = _get_fill_state(batch_id)
    if state is None:
        raise HTTPException(404, detail="Batch not found")

    template = manager.get(state.get("template_id", ""))
    if template is None:
        raise HTTPException(500, detail="Template data not available")

    fields = template.get("fields", [])
    adjustments = state.get("adjustments", {}).get(str(index), {})
    page_zero = page - 1
    result = []
    for f in fields:
        if f.get("type") != "text" and f["page"] != page_zero:
            continue
        adj = adjustments.get(f["column"], {})
        result.append({
            "column": f["column"],
            "page": page,
            "x": point_to_pixel(adj.get("x", f["x"])),
            "y": point_to_pixel(adj.get("y", f["y"])),
            "font_size": adj.get("font_size", f["font_size"]),
            "max_width": f.get("max_width"),
            "type": f.get("type", "column"),
        })
    return result


@router.post("/{batch_id}/adjust/{index}")
async def adjust_field(
    batch_id: str, index: int, req: AdjustFieldRequest
) -> dict[str, bool]:
    state = _get_fill_state(batch_id)
    if state is None:
        raise HTTPException(404, detail="Batch not found")
    if state["status"] != "completed":
        raise HTTPException(400, detail="Batch not yet completed")

    template_id = state.get("template_id", "")
    template = manager.get(template_id)
    if template is None:
        raise HTTPException(500, detail="Template data not available")

    excel_path = Path(state["excel_path"])
    _, rows = read_rows(excel_path)
    files: list[str] = state.get("files", [])
    if index < 1 or index > len(files):
        raise HTTPException(400, detail="File index out of range")
    if index - 1 >= len(rows):
        raise HTTPException(400, detail="Row data not available for this index")
    row = rows[index - 1]

    with _fill_state_lock:
        file_adjs = fill_state[batch_id].setdefault("adjustments", {}).setdefault(str(index), {})
        existing = file_adjs.get(req.column, {})
        if req.font_size is not None:
            existing["font_size"] = req.font_size
        if req.x is not None:
            existing["x"] = pixel_to_point(req.x)
        if req.y is not None:
            existing["y"] = pixel_to_point(req.y)
        existing["page_adjusted"] = req.page - 1
        file_adjs[req.column] = existing

    fields = template.get("fields", [])
    adjusted_fields = []
    for f in fields:
        adj = file_adjs.get(f["column"], {})
        fc = dict(f)
        if "font_size" in adj:
            fc["font_size"] = adj["font_size"]
        if "x" in adj:
            fc["x"] = adj["x"]
        if "y" in adj:
            fc["y"] = adj["y"]
        adjusted_fields.append(fc)

    pdf_file = template.get("pdf_file", "")
    pdf_path = UPLOAD_DIR / pdf_file
    output_dir = Path(state["output_dir"])
    output_path = output_dir / files[index - 1]

    overlay_fields(pdf_path, adjusted_fields, row, output_path)

    preview_cache_dir = GENERATED_PREVIEW_CACHE / batch_id
    if preview_cache_dir.exists():
        for f in preview_cache_dir.glob("*.png"):
            f.unlink()

    return {"ok": True}
