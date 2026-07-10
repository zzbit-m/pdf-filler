from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.models import (
    TemplateRenameRequest,
    WorkflowListItem,
    WorkflowSaveRequest,
    WorkflowSaveResponse,
)
from app.services.template_manager import TemplateManager
from app.services.workflow_manager import WorkflowManager

router = APIRouter(prefix="/workflow", tags=["workflow"])

TEMPLATES_DIR = Path("data/templates")
WORKFLOWS_DIR = Path("data/workflows")
workflow_mgr = WorkflowManager(WORKFLOWS_DIR)
template_mgr = TemplateManager(TEMPLATES_DIR)


@router.post("", response_model=WorkflowSaveResponse)
async def create_workflow(req: WorkflowSaveRequest) -> WorkflowSaveResponse:
    seen: set[str] = set()
    for route in req.routes:
        if route.value in seen:
            raise HTTPException(400, detail=f"Duplicate route value: {route.value}")
        seen.add(route.value)

    routes = [
        {"value": r.value, "template_id": r.template_id} for r in req.routes
    ]
    workflow_id = workflow_mgr.save(
        name=req.name, routing_column=req.routing_column, routes=routes
    )
    workflow = workflow_mgr.get(workflow_id)
    assert workflow is not None
    return WorkflowSaveResponse(
        id=workflow["id"],
        name=workflow["name"],
        routing_column=workflow["routing_column"],
        route_count=len(workflow["routes"]),
        created_at=workflow["created_at"],
    )


@router.get("/list", response_model=list[WorkflowListItem])
async def list_workflows() -> list[WorkflowListItem]:
    return [WorkflowListItem(**w) for w in workflow_mgr.list_all()]


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str) -> dict[str, Any]:
    workflow = workflow_mgr.get(workflow_id)
    if workflow is None:
        raise HTTPException(404, detail="Workflow not found")
    routes = workflow.get("routes", [])
    expanded = []
    for route in routes:
        tmpl = template_mgr.get(route["template_id"])
        expanded.append({
            "value": route["value"],
            "template_id": route["template_id"],
            "template_name": tmpl["name"] if tmpl else "(deleted)",
        })
    workflow["routes"] = expanded
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowListItem)
async def rename_workflow(
    workflow_id: str, req: TemplateRenameRequest
) -> WorkflowListItem:
    workflow = workflow_mgr.get(workflow_id)
    if workflow is None:
        raise HTTPException(404, detail="Workflow not found")
    if not workflow_mgr.rename(workflow_id, req.name):
        raise HTTPException(404, detail="Workflow not found")
    updated = workflow_mgr.get(workflow_id)
    assert updated is not None
    return WorkflowListItem(
        id=updated["id"],
        name=updated["name"],
        routing_column=updated["routing_column"],
        route_count=len(updated.get("routes", [])),
        created_at=updated["created_at"],
    )


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str) -> dict[str, bool]:
    if not workflow_mgr.delete(workflow_id):
        raise HTTPException(404, detail="Workflow not found")
    return {"ok": True}
