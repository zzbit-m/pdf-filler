import fitz
import pytest

from app.services.auto_position import (
    _combined_score,
    _substring_boost,
    _word_overlap,
    extract_labels,
    suggest_positions,
)


@pytest.fixture
def pdf_with_labels(tmp_path):
    path = tmp_path / "labels.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 100), "Name-Surname", fontsize=10)
    page.insert_text((50, 150), "Department", fontsize=10)
    page.insert_text((50, 200), "Salary", fontsize=10)
    page.insert_text((50, 250), "Date of Birth", fontsize=10)
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def empty_pdf(tmp_path):
    path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def corrupted_pdf(tmp_path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"not a pdf")
    return str(path)


class TestExtractLabels:
    def test_extracts_labels(self, pdf_with_labels):
        labels = extract_labels(pdf_with_labels, 0)
        texts = [lab["text"] for lab in labels]
        assert "Name-Surname" in texts
        assert "Department" in texts
        assert "Salary" in texts
        assert "Date of Birth" in texts

    def test_coordinates_in_points(self, pdf_with_labels):
        labels = extract_labels(pdf_with_labels, 0)
        name = [lab for lab in labels if lab["text"] == "Name-Surname"][0]
        assert abs(name["x0"] - 50) < 2
        assert abs(name["y0"] - 100) < 15
        assert name["x1"] > name["x0"]

    def test_empty_page_returns_empty(self, empty_pdf):
        assert extract_labels(empty_pdf, 0) == []

    def test_out_of_range_raises(self, pdf_with_labels):
        with pytest.raises(ValueError, match="out of range"):
            extract_labels(pdf_with_labels, 99)

    def test_corrupted_pdf_raises(self, corrupted_pdf):
        with pytest.raises(ValueError, match="Cannot open PDF"):
            extract_labels(corrupted_pdf, 0)


class TestScoring:
    def test_exact_match_ratio(self):
        score = _combined_score("Name", "Name")
        assert score >= 1.0

    def test_substring_boost_helps_hyphen(self):
        score = _combined_score("Name", "Name-Surname")
        assert score > 0.6

    def test_substring_boost_helps(self):
        score = _combined_score("Name", "GivenName")
        assert score > 0.6

    def test_unrelated_below_threshold(self):
        score = _combined_score("Salary", "Date of Birth")
        assert score < 0.5

    def test_word_overlap_identical_words(self):
        assert _word_overlap("Given Name", "Name") > 0

    def test_word_overlap_no_match(self):
        assert _word_overlap("Salary", "Date of Birth") == 0.0

    def test_substring_boost_triggered(self):
        assert _substring_boost("Name", "Name-Surname") == 0.15

    def test_substring_boost_not_triggered(self):
        assert _substring_boost("Salary", "Department") == 0.0


class TestSuggestPositions:
    def test_suggests_matching_columns(self, pdf_with_labels):
        labels = extract_labels(pdf_with_labels, 0)
        cols = ["Name-Surname", "Department", "Salary"]
        results = suggest_positions(labels, cols)
        found = {r["column"] for r in results}
        assert found == {"Name-Surname", "Department", "Salary"}

    def test_skips_unmatched_columns(self, pdf_with_labels):
        labels = extract_labels(pdf_with_labels, 0)
        results = suggest_positions(labels, ["Nonexistent"])
        assert results == []

    def test_returns_coordinates(self, pdf_with_labels):
        labels = extract_labels(pdf_with_labels, 0)
        results = suggest_positions(labels, ["Name-Surname"])
        r = results[0]
        assert r["x"] > 0
        assert r["y"] > 0
        assert "confidence" in r

    def test_position_is_right_of_label(self, pdf_with_labels):
        labels = extract_labels(pdf_with_labels, 0)
        name_label = [lab for lab in labels if lab["text"] == "Name-Surname"][0]
        results = suggest_positions(labels, ["Name-Surname"])
        r = results[0]
        assert r["x"] > name_label["x0"]
        assert abs(r["x"] - (name_label["x1"] + 8)) < 0.01
        assert abs(r["y"] - name_label["y0"]) < 15

    def test_sorted_by_confidence(self, pdf_with_labels):
        labels = extract_labels(pdf_with_labels, 0)
        cols = ["Department", "Salary", "Name-Surname"]
        results = suggest_positions(labels, cols)
        confidences = [r["confidence"] for r in results]
        assert confidences == sorted(confidences, reverse=True)

    def test_no_duplicate_columns(self, pdf_with_labels):
        labels = extract_labels(pdf_with_labels, 0)
        cols = ["Name-Surname", "Department"]
        results = suggest_positions(labels, cols)
        columns = [r["column"] for r in results]
        assert len(columns) == len(set(columns))

    def test_no_labels_returns_empty(self, empty_pdf):
        assert suggest_positions(extract_labels(empty_pdf, 0), ["Name"]) == []

    def test_custom_threshold_higher(self, pdf_with_labels):
        labels = extract_labels(pdf_with_labels, 0)
        cols = ["Name-Surname", "Nonexistent"]
        results = suggest_positions(labels, cols, threshold=0.9)
        assert len(results) == 1
        assert results[0]["column"] == "Name-Surname"
