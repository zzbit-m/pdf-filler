import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import DATA_BASE
from app.schemas.models import FillStartResponse, FillStatusResponse
from app.services.excel_reader import read_rows
from app.services.pdf_overlay import overlay_fields
from app.services.pdf_preview import render_preview
from app.services.template_manager import TemplateManager
from app.services.workflow_manager import WorkflowManager

router = APIRouter(prefix="/fill", tags=["fill"])

UPLOAD_DIR = DATA_BASE / "uploads"
TEMPLATES_DIR = DATA_BASE / "templates"
WORKFLOWS_DIR = DATA_BASE / "workflows"
OUTPUT_DIR = DATA_BASE / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_PREVIEW_CACHE = DATA_BASE / "preview_cache" / "generated"

ALLOWED_EXCEL = {".xlsx", ".xlsm"}

manager = TemplateManager(TEMPLATES_DIR)
workflow_mgr = WorkflowManager(WORKFLOWS_DIR)

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
        fields = template.get("fields", [])
        if not fields:
            _set_fill_state(batch_id, {"status": "error", "error": "Template has no fields"})
            return
        pdf_file = template.get("pdf_file", "")
        pdf_path = UPLOAD_DIR / pdf_file

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
            except Exception as exc:
                err_msg = str(exc)
                _set_fill_state(batch_id, {
                    "status": "error", "total": total, "completed": i, "error": err_msg,
                })
                return
            _set_fill_state(batch_id, {"status": "processing", "total": total, "completed": i + 1})

        _set_fill_state(batch_id, {
            "status": "completed",
            "total": total,
            "completed": total,
            "output_dir": str(batch_output),
            "files": files,
            "warnings": [],
        })
    except Exception as exc:
        _set_fill_state(batch_id, {"status": "error", "error": str(exc)})


def _run_workflow_batch(
    batch_id: str, workflow: dict[str, Any], excel_path: Path, tmpl_mgr: TemplateManager
) -> None:
    try:
        _, rows = read_rows(excel_path)
        routing_column: str = workflow.get("routing_column", "")
        routes: dict[str, str] = {r["value"]: r["template_id"] for r in workflow.get("routes", [])}
        template_cache: dict[str, dict[str, Any]] = {}

        batch_output = OUTPUT_DIR / batch_id
        batch_output.mkdir(parents=True, exist_ok=True)

        total = len(rows)
        warnings: list[str] = []
        files: list[str] = []
        for i, row in enumerate(rows):
            routing_value = row.get(routing_column, "").strip()
            if not routing_value:
                warnings.append(f"Row {i + 1}: empty routing value, skipped")
                _set_fill_state(batch_id, {
                    "status": "processing", "total": total,
                    "completed": i + 1, "warnings": warnings,
                })
                continue
            template_id = routes.get(routing_value)
            if template_id is None:
                warnings.append(f"Row {i + 1}: no route for '{routing_value}', skipped")
                _set_fill_state(batch_id, {
                    "status": "processing", "total": total,
                    "completed": i + 1, "warnings": warnings,
                })
                continue

            if template_id not in template_cache:
                tmpl = tmpl_mgr.get(template_id)
                if tmpl is None:
                    warnings.append(f"Row {i + 1}: template '{template_id}' not found, skipped")
                    _set_fill_state(batch_id, {
                        "status": "processing", "total": total,
                        "completed": i + 1, "warnings": warnings,
                    })
                    continue
                template_cache[template_id] = tmpl
            template = template_cache[template_id]

            fields = template.get("fields", [])
            if not fields:
                warnings.append(f"Row {i + 1}: template '{template_id}' has no fields, skipped")
                _set_fill_state(batch_id, {
                    "status": "processing", "total": total,
                    "completed": i + 1, "warnings": warnings,
                })
                continue
            pdf_file = template.get("pdf_file", "")
            pdf_path = UPLOAD_DIR / pdf_file
            safe = _sanitize_filename(routing_value)
            filename = f"{i + 1}_{safe}.pdf"
            output_path = batch_output / filename
            try:
                overlay_fields(pdf_path, fields, row, output_path)
                files.append(filename)
            except Exception as exc:
                _set_fill_state(batch_id, {
                    "status": "error", "total": total, "completed": i,
                    "error": str(exc), "warnings": warnings,
                })
                return
            _set_fill_state(batch_id, {
                "status": "processing", "total": total, "completed": i + 1, "warnings": warnings,
            })

        _set_fill_state(batch_id, {
            "status": "completed", "total": total, "completed": total,
            "output_dir": str(batch_output), "warnings": warnings,
            "files": files,
        })
    except Exception as exc:
        _set_fill_state(batch_id, {"status": "error", "error": str(exc)})


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
    template_columns = {f["column"] for f in template["fields"]}
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


@router.post("/workflow", response_model=FillStartResponse)
async def start_workflow_fill(
    workflow_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
) -> FillStartResponse:
    workflow = workflow_mgr.get(workflow_id)
    if workflow is None:
        raise HTTPException(404, detail="Workflow not found")

    if not workflow.get("routes"):
        raise HTTPException(400, detail="Workflow has no routes")

    if not file.filename or Path(file.filename).suffix.lower() not in ALLOWED_EXCEL:
        raise HTTPException(400, detail="Only .xlsx and .xlsm files are accepted")

    excel_path = UPLOAD_DIR / f"{uuid.uuid4()}.xlsx"
    content = await file.read()
    excel_path.write_bytes(content)

    excel_columns, rows = read_rows(excel_path)
    routing_column: str = workflow["routing_column"]
    if routing_column not in excel_columns:
        raise HTTPException(400, detail=f"Routing column '{routing_column}' not found in Excel")

    warnings: list[str] = []
    route_values = {r["value"] for r in workflow["routes"]}
    unknown_values: set[str] = set()
    for row in rows:
        v = row.get(routing_column, "").strip()
        if v and v not in route_values:
            unknown_values.add(v)
    if unknown_values:
        warnings.append(f"Unmapped routing values: {', '.join(sorted(unknown_values))}")

    batch_id = str(uuid.uuid4())
    _set_fill_state(
        batch_id, {"status": "pending", "total": 0, "completed": 0, "warnings": warnings}
    )
    background_tasks.add_task(_run_workflow_batch, batch_id, workflow, excel_path, manager)

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
