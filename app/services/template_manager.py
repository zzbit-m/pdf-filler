import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PDF_FILE_RE = re.compile(r"^[0-9a-f-]+\.pdf$")
_TEMPLATE_ID_RE = re.compile(r"^[0-9a-f-]+$")


class TemplateManager:
    def __init__(self, templates_dir: str | Path):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, template_id: str) -> Path:
        if not _TEMPLATE_ID_RE.match(template_id):
            raise ValueError(f"Invalid template_id: {template_id}")
        return self.templates_dir / f"{template_id}.json"

    def save(self, name: str, pdf_file: str, fields: list[dict[str, Any]]) -> str:
        template_id = str(uuid.uuid4())
        template = {
            "id": template_id,
            "name": name,
            "pdf_file": pdf_file,
            "version": 1,
            "fields": fields,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._path(template_id).write_text(
            json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return template_id

    def list_all(self) -> list[dict[str, Any]]:
        templates = []
        for f in sorted(self.templates_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            templates.append({
                "id": data["id"],
                "name": data["name"],
                "pdf_file": data["pdf_file"],
                "version": data["version"],
                "created_at": data.get("created_at", ""),
                "field_count": len(data.get("fields", [])),
            })
        return templates

    def get(self, template_id: str) -> dict[str, Any] | None:
        path = self._path(template_id)
        if not path.exists():
            return None
        try:
            result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return result
        except (json.JSONDecodeError, OSError):
            return None

    def rename(self, template_id: str, new_name: str) -> bool:
        template = self.get(template_id)
        if template is None:
            return False
        template["name"] = new_name
        self._path(template_id).write_text(
            json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True

    def duplicate(self, template_id: str, name: str | None = None) -> dict[str, Any] | None:
        src = self.get(template_id)
        if src is None:
            return None
        new_id = str(uuid.uuid4())
        new_name = name or f"{src['name']} (Copy)"
        template = {k: v for k, v in src.items() if k not in {"id", "created_at"}}
        template["id"] = new_id
        template["name"] = new_name
        template["created_at"] = datetime.now(timezone.utc).isoformat()
        self._path(new_id).write_text(
            json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return template

    def delete(self, template_id: str) -> bool:
        path = self._path(template_id)
        if not path.exists():
            return False
        path.unlink()
        return True
