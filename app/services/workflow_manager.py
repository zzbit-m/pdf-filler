import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_WORKFLOW_ID_RE = re.compile(r"^[0-9a-f-]+$")


class WorkflowManager:
    def __init__(self, workflows_dir: str | Path):
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, workflow_id: str) -> Path:
        if not _WORKFLOW_ID_RE.match(workflow_id):
            raise ValueError(f"Invalid workflow_id: {workflow_id}")
        return self.workflows_dir / f"{workflow_id}.json"

    def save(self, name: str, routing_column: str, routes: list[dict[str, str]]) -> str:
        workflow_id = str(uuid.uuid4())
        workflow = {
            "id": workflow_id,
            "name": name,
            "routing_column": routing_column,
            "routes": routes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._path(workflow_id).write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return workflow_id

    def list_all(self) -> list[dict[str, Any]]:
        workflows = []
        for fpath in sorted(self.workflows_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            workflows.append({
                "id": data["id"],
                "name": data["name"],
                "routing_column": data["routing_column"],
                "route_count": len(data.get("routes", [])),
                "created_at": data.get("created_at", ""),
            })
        return workflows

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        path = self._path(workflow_id)
        if not path.exists():
            return None
        try:
            result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return result
        except (json.JSONDecodeError, OSError):
            return None

    def rename(self, workflow_id: str, new_name: str) -> bool:
        workflow = self.get(workflow_id)
        if workflow is None:
            return False
        workflow["name"] = new_name
        self._path(workflow_id).write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True

    def delete(self, workflow_id: str) -> bool:
        path = self._path(workflow_id)
        if not path.exists():
            return False
        path.unlink()
        return True
