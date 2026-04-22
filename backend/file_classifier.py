"""Automatic file classification for data/ inputs (no fixed filenames)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


def _pdf_first_page_text(path: Path) -> str:
    try:
        import fitz  # pymupdf

        with fitz.open(path) as doc:
            if len(doc) == 0:
                return ""
            return (doc[0].get_text() or "").lower()
    except Exception:
        return ""


def _score_file(path: Path, lowered_name: str, pdf_text: str) -> Dict[str, int]:
    score = {"layout": 0, "excel": 0, "reference": 0, "gad": 0, "structure": 0}
    ext = path.suffix.lower()
    text = f"{lowered_name} {pdf_text}"

    if ext == ".xlsx":
        score["excel"] += 100

    if ext in {".png", ".jpg", ".jpeg", ".pdf"}:
        if any(k in text for k in ("layout", "plan", "plot", "general arrangement", "arrangement")):
            score["layout"] += 20
        if any(k in text for k in ("structure", "wall", "civil", "building", "room")):
            score["structure"] += 20
        if "gad" in text or "typical" in text:
            score["gad"] += 30
        if any(k in text for k in ("reference", "section", "detail")):
            score["reference"] += 20

    # OCR-like keyword hints from PDF text
    if any(k in text for k in ("b200", "e100", "p001a", "x100")):
        score["layout"] += 25
    if any(k in text for k in ("ø1200", "o1200", "section")):
        score["reference"] += 25

    # practical defaults by extension when still ambiguous
    if ext in {".png", ".jpg", ".jpeg"}:
        score["layout"] += 5
    if ext == ".pdf":
        score["reference"] += 5

    return score


def classify_files(data_dir: Path) -> Dict[str, Optional[str]]:
    """
    Classify arbitrary user files in data/ into:
      layout, excel, reference, gad, structure
    """
    files = [p for p in data_dir.iterdir() if p.is_file() and p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".xlsx"}]
    scored: List[tuple[Path, Dict[str, int]]] = []
    for p in files:
        name = p.name.lower()
        pdf_text = _pdf_first_page_text(p) if p.suffix.lower() == ".pdf" else ""
        scored.append((p, _score_file(p, name, pdf_text)))

    out: Dict[str, Optional[str]] = {"layout": None, "excel": None, "reference": None, "gad": None, "structure": None}
    used: set[Path] = set()
    for kind in ("excel", "layout", "structure", "gad", "reference"):
        best_path: Optional[Path] = None
        best_score = -1
        for p, s in scored:
            if p in used:
                continue
            if s[kind] > best_score:
                best_score = s[kind]
                best_path = p
        if best_path is not None and best_score > 0:
            out[kind] = str(best_path)
            used.add(best_path)
    return out

