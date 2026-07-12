from pathlib import Path

from app.services.workflow_manager import WorkflowManager


class TestWorkflowManager:
    def test_save_and_get(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        wid = mgr.save("Test WF", "Department", [
            {"value": "Eng", "template_id": "t1"},
            {"value": "HR", "template_id": "t2"},
        ])

        loaded = mgr.get(wid)
        assert loaded is not None
        assert loaded["name"] == "Test WF"
        assert loaded["routing_column"] == "Department"
        assert len(loaded["routes"]) == 2
        assert loaded["routes"][0]["value"] == "Eng"

    def test_list_workflows(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        mgr.save("A", "ColA", [{"value": "x", "template_id": "t1"}])
        mgr.save("B", "ColB", [{"value": "y", "template_id": "t2"}])

        all_w = mgr.list_all()
        assert len(all_w) == 2
        names = [w["name"] for w in all_w]
        assert "A" in names
        assert "B" in names

    def test_list_empty(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        assert mgr.list_all() == []

    def test_get_nonexistent(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        assert mgr.get("00000000-0000-0000-0000-000000000000") is None

    def test_delete_existing(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        wid = mgr.save("To Delete", "C", [{"value": "a", "template_id": "t1"}])
        assert mgr.delete(wid) is True
        assert mgr.get(wid) is None

    def test_delete_nonexistent(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        assert mgr.delete("00000000-0000-0000-0000-000000000000") is False

    def test_rename_existing(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        wid = mgr.save("Old", "C", [{"value": "a", "template_id": "t1"}])
        assert mgr.rename(wid, "New Name") is True
        loaded = mgr.get(wid)
        assert loaded is not None
        assert loaded["name"] == "New Name"

    def test_rename_nonexistent(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        assert mgr.rename("00000000-0000-0000-0000-000000000000", "X") is False

    def test_list_all_skips_corrupt_file(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        wid = mgr.save("Good", "C", [{"value": "a", "template_id": "t1"}])
        corrupt = workflows_dir / "corrupt.json"
        corrupt.write_text("{bad json", encoding="utf-8")
        all_w = mgr.list_all()
        ids = [w["id"] for w in all_w]
        assert wid in ids

    def test_get_corrupt_file_returns_none(self, workflows_dir: Path) -> None:
        mgr = WorkflowManager(workflows_dir)
        wid = mgr.save("Good", "C", [{"value": "a", "template_id": "t1"}])
        path = mgr._path(wid)
        path.write_text("{bad json", encoding="utf-8")
        assert mgr.get(wid) is None
