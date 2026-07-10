from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

import fitz


def extract_labels(pdf_path: str, page_num: int) -> list[dict[str, Any]]:
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ValueError(f"Cannot open PDF: {e}")

    if page_num < 0 or page_num >= len(doc):
        doc.close()
        raise ValueError(f"Page {page_num} out of range")

    page = doc[page_num]
    words = page.get_text("words")
    doc.close()

    if not words:
        return []

    lines: dict[tuple[int, int], dict[str, Any]] = defaultdict(
        lambda: {"text": [], "x0": float("inf"), "y0": float("inf"), "x1": 0.0, "y1": 0.0}
    )

    for w in words:
        x0, y0, x1, y1, word, block_no, line_no = w[:7]
        key = (int(block_no), int(line_no))
        lines[key]["text"].append(word)
        lines[key]["x0"] = min(lines[key]["x0"], x0)
        lines[key]["y0"] = min(lines[key]["y0"], y0)
        lines[key]["x1"] = max(lines[key]["x1"], x1)
        lines[key]["y1"] = max(lines[key]["y1"], y1)

    labels: list[dict[str, Any]] = []
    for data in lines.values():
        text = " ".join(data["text"]).strip()
        if not text or len(text) > 100:
            continue
        labels.append({
            "text": text,
            "x0": data["x0"],
            "y0": data["y0"],
            "x1": data["x1"],
            "y1": data["y1"],
        })

    return labels


def _word_overlap(a: str, b: str) -> float:
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return max(len(intersection) / len(words_a), len(intersection) / len(words_b))


def _substring_boost(a: str, b: str) -> float:
    low_a, low_b = a.lower(), b.lower()
    if low_a in low_b or low_b in low_a:
        return 0.15
    return 0.0


def _combined_score(col: str, label_text: str) -> float:
    col_low, label_low = col.lower(), label_text.lower()
    seq = SequenceMatcher(None, col_low, label_low).ratio()
    overlap = _word_overlap(col, label_text)
    boost = _substring_boost(col, label_text)
    return max(seq, overlap) + boost


def suggest_positions(
    labels: list[dict[str, Any]], columns: list[str], threshold: float = 0.7
) -> list[dict[str, Any]]:
    used_columns: set[str] = set()
    results: list[dict[str, Any]] = []

    for label in labels:
        best_score = 0.0
        best_col = None
        for col in columns:
            if col in used_columns:
                continue
            score = _combined_score(col, label["text"])
            if score > best_score:
                best_score = score
                best_col = col

        if best_col and best_score >= threshold:
            used_columns.add(best_col)
            results.append({
                "column": best_col,
                "x": label["x1"] + 8,
                "y": label["y0"],
                "confidence": round(best_score, 3),
            })

    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results
