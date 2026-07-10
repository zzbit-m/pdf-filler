import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.schemas.models import FillStartResponse, FillStatusResponse
from app.services.excel_reader import read_rows
from app.services.pdf_overlay import overlay_fields
from app.services.template_manager import TemplateManager
from app.services.workflow_manager import WorkflowManager

router = APIRouter(prefix="/fill", tags=["fill"])

UPLOAD_DIR = Path("data/uploads")
TEMPLATES_DIR = Path("data/templates")
WORKFLOWS_DIR = Path("data/workflows")
OUTPUT_DIR = Path("data/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

manager = TemplateManager(TEMPLATES_DIR)
workflow_mgr = WorkflowManager(WORKFLOWS_DIR)

fill_state: dict[str, dict[str, Any]] = {}


def _sanitize_filename(value: str) -> str:
    return re.sub(r"[^\w\-]", "_", value)[:100]


def _run_batch(batch_id: str, template: dict[str, Any], excel_path: Path) -> None:
    _, rows = read_rows(excel_path)
    fields = template["fields"]
    pdf_path = UPLOAD_DIR / template["pdf_file"]

    batch_output = OUTPUT_DIR / batch_id
    batch_output.mkdir(parents=True, exist_ok=True)

    total = len(rows)
    for i, row in enumerate(rows):
        try:
            output_path = batch_output / f"employee_{i + 1}.pdf"
            overlay_fields(pdf_path, fields, row, output_path)
        except Exception as exc:
            err_msg = str(exc)
            fill_state[batch_id] = {
                "status": "error", "total": total, "completed": i, "error": err_msg,
            }
            return
        fill_state[batch_id] = {"status": "processing", "total": total, "completed": i + 1}

    fill_state[batch_id] = {
        "status": "completed",
        "total": total,
        "completed": total,
        "output_dir": str(batch_output),
    }


def _run_workflow_batch(
    batch_id: str, workflow: dict[str, Any], excel_path: Path, tmpl_mgr: TemplateManager
) -> None:
    _, rows = read_rows(excel_path)
    routing_column: str = workflow["routing_column"]
    routes: dict[str, str] = {r["value"]: r["template_id"] for r in workflow["routes"]}

    batch_output = OUTPUT_DIR / batch_id
    batch_output.mkdir(parents=True, exist_ok=True)

    total = len(rows)
    warnings: list[str] = []
    for i, row in enumerate(rows):
        routing_value = row.get(routing_column, "").strip()
        if not routing_value:
            warnings.append(f"Row {i + 1}: empty routing value, skipped")
            fill_state[batch_id] = {
                "status": "processing", "total": total, "completed": i + 1, "warnings": warnings,
            }
            continue
        template_id = routes.get(routing_value)
        if template_id is None:
            warnings.append(f"Row {i + 1}: no route for '{routing_value}', skipped")
            fill_state[batch_id] = {
                "status": "processing", "total": total, "completed": i + 1, "warnings": warnings,
            }
            continue
        template = tmpl_mgr.get(template_id)
        if template is None:
            warnings.append(f"Row {i + 1}: template '{template_id}' not found, skipped")
            fill_state[batch_id] = {
                "status": "processing", "total": total, "completed": i + 1, "warnings": warnings,
            }
            continue

        fields = template["fields"]
        pdf_path = UPLOAD_DIR / template["pdf_file"]
        safe = _sanitize_filename(routing_value)
        output_path = batch_output / f"{i + 1}_{safe}.pdf"
        try:
            overlay_fields(pdf_path, fields, row, output_path)
        except Exception as exc:
            fill_state[batch_id] = {
                "status": "error", "total": total, "completed": i,
                "error": str(exc), "warnings": warnings,
            }
            return
        fill_state[batch_id] = {
            "status": "processing", "total": total, "completed": i + 1, "warnings": warnings,
        }

    fill_state[batch_id] = {
        "status": "completed", "total": total, "completed": total,
        "output_dir": str(batch_output), "warnings": warnings,
    }


@router.post("", response_model=FillStartResponse)
async def start_fill(
    template_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
) -> FillStartResponse:
    template = manager.get(template_id)
    if template is None:
        raise HTTPException(404, detail="Template not found")

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, detail="Only .xlsx files are accepted")

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
    fill_state[batch_id] = {"status": "pending", "total": 0, "completed": 0, "warnings": warnings}
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

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, detail="Only .xlsx files are accepted")

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
    fill_state[batch_id] = {"status": "pending", "total": 0, "completed": 0, "warnings": warnings}
    background_tasks.add_task(_run_workflow_batch, batch_id, workflow, excel_path, manager)

    return FillStartResponse(batch_id=batch_id, warnings=warnings)


@router.get("/{batch_id}/status", response_model=FillStatusResponse)
async def fill_status(batch_id: str) -> FillStatusResponse:
    state = fill_state.get(batch_id)
    if state is None:
        raise HTTPException(404, detail="Batch not found")
    return FillStatusResponse(
        batch_id=batch_id,
        status=state["status"],
        completed=state["completed"],
        total=state["total"],
        error=state.get("error"),
        warnings=state.get("warnings", []),
    )


@router.get("/{batch_id}/download")
async def fill_download(batch_id: str) -> FileResponse:
    state = fill_state.get(batch_id)
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
