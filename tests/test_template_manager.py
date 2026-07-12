from pathlib import Path

from app.services.template_manager import TemplateManager


class TestTemplateManager:
    def test_save_and_get(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        tid = mgr.save("Test Template", "some.pdf", [
            {"column": "Name", "page": 1, "x": 100, "y": 200, "font_size": 11},
        ])

        loaded = mgr.get(tid)
        assert loaded is not None
        assert loaded["name"] == "Test Template"
        assert loaded["pdf_file"] == "some.pdf"
        assert len(loaded["fields"]) == 1
        assert loaded["fields"][0]["column"] == "Name"

    def test_list_templates(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        mgr.save("A", "a.pdf", [])
        mgr.save("B", "b.pdf", [])

        all_t = mgr.list_all()
        assert len(all_t) == 2
        names = [t["name"] for t in all_t]
        assert "A" in names
        assert "B" in names

    def test_list_empty(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        assert mgr.list_all() == []

    def test_get_nonexistent(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        assert mgr.get("00000000-0000-0000-0000-000000000000") is None

    def test_delete_existing(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        tid = mgr.save("To Delete", "x.pdf", [])
        assert mgr.delete(tid) is True
        assert mgr.get(tid) is None

    def test_delete_nonexistent(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        assert mgr.delete("00000000-0000-0000-0000-000000000000") is False

    def test_rename_existing(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        tid = mgr.save("Old Name", "x.pdf", [])
        assert mgr.rename(tid, "New Name") is True
        loaded = mgr.get(tid)
        assert loaded is not None
        assert loaded["name"] == "New Name"

    def test_rename_nonexistent(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        assert mgr.rename("00000000-0000-0000-0000-000000000000", "X") is False

    def test_duplicate_existing(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        tid = mgr.save("Original", "x.pdf", [
            {"column": "Name", "page": 1, "x": 100, "y": 200, "font_size": 11},
        ])
        dup = mgr.duplicate(tid)
        assert dup is not None
        assert dup["id"] != tid
        assert dup["name"] == "Original (Copy)"
        assert dup["pdf_file"] == "x.pdf"
        assert len(dup["fields"]) == 1

    def test_duplicate_nonexistent(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        assert mgr.duplicate("00000000-0000-0000-0000-000000000000") is None

    def test_duplicate_custom_name(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        tid = mgr.save("Original", "x.pdf", [])
        dup = mgr.duplicate(tid, name="Custom Copy")
        assert dup is not None
        assert dup["name"] == "Custom Copy"

    def test_list_all_skips_corrupt_file(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        fields = [{"column": "A", "page": 1, "x": 1, "y": 2, "font_size": 11}]
        tid = mgr.save("Good", "g.pdf", fields)
        corrupt = templates_dir / "corrupt.json"
        corrupt.write_text("{bad json", encoding="utf-8")
        all_t = mgr.list_all()
        ids = [t["id"] for t in all_t]
        assert tid in ids

    def test_list_all_skips_file_missing_name_key(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        fields = [{"column": "A", "page": 1, "x": 1, "y": 2, "font_size": 11}]
        tid = mgr.save("Good", "g.pdf", fields)
        bad = templates_dir / "no_name.json"
        bad.write_text('{"id": "x", "pdf_file": "x.pdf", "version": 1}', encoding="utf-8")
        all_t = mgr.list_all()
        ids = [t["id"] for t in all_t]
        assert tid in ids
        assert "x" not in ids

    def test_get_corrupt_file_returns_none(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        tid = mgr.save("Good", "g.pdf", [])
        path = mgr._path(tid)
        path.write_text("{bad json", encoding="utf-8")
        assert mgr.get(tid) is None

    def test_get_malformed_id_returns_none(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        assert mgr.get("not-a-valid-id!!") is None

    def test_delete_malformed_id_returns_false(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        assert mgr.delete("not-a-valid-id!!") is False

    def test_rename_malformed_id_returns_false(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        assert mgr.rename("not-a-valid-id!!", "X") is False

    def test_duplicate_malformed_id_returns_none(self, templates_dir: Path) -> None:
        mgr = TemplateManager(templates_dir)
        assert mgr.duplicate("not-a-valid-id!!") is None
