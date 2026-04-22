"""Locate equipment tag positions with confidence and fallback chain."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, Tuple

import cv2

from backend.pickpoint import pick_points_on_plan

_TAG_PATTERN = re.compile(r"[A-Z]\s*\d{2,4}\s*[A-Z]?", re.IGNORECASE)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_plan_path() -> Path:
    runtime_plan = _repo_root() / "data" / "runtime" / "plan.png"
    if runtime_plan.is_file():
        img = cv2.imread(str(runtime_plan), cv2.IMREAD_COLOR)
        if img is not None:
            return runtime_plan
    default_plan = _repo_root() / "data" / "plan_hd.png"
    if default_plan.is_file():
        return default_plan
    if runtime_plan.is_file():
        return runtime_plan
    return default_plan


def _normalize_tag(text: str) -> str:
    return "".join(text.upper().split())


def _extract_candidate_tags(text: str) -> Iterable[str]:
    for m in _TAG_PATTERN.finditer(text or ""):
        t = _normalize_tag(m.group(0))
        if t:
            yield t


def _is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def _detect_with_easyocr(plan_path: Path) -> Dict[str, Dict[str, object]]:
    import easyocr  # optional dependency, imported lazily

    reader = easyocr.Reader(["en"], gpu=False)
    results = reader.readtext(str(plan_path))
    out: Dict[str, Dict[str, object]] = {}
    conf_map: Dict[str, float] = {}
    for item in results:
        # item: [bbox, text, confidence]
        bbox, text, confidence = item
        tags = list(_extract_candidate_tags(str(text)))
        if not tags:
            continue
        cx = int(sum(p[0] for p in bbox) / len(bbox))
        cy = int(sum(p[1] for p in bbox) / len(bbox))
        for tag in tags:
            prev_conf = conf_map.get(tag, -1.0)
            if float(confidence) >= prev_conf:
                conf_map[tag] = float(confidence)
                out[tag] = {
                    "pos": [cx, cy],
                    "confidence": max(0.0, min(1.0, float(confidence))),
                    "source": "ocr",
                }
    return out


def _detect_with_pdf_text_layer(pdf_path: Path) -> Dict[str, Dict[str, object]]:
    """Extract tag locations from PDF text layer (fallback 2)."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    out: Dict[str, Dict[str, object]] = {}
    try:
        if len(doc) == 0:
            return out
        page = doc[0]
        words = page.get_text("words")
        for w in words:
            x0, y0, x1, y1, text = w[:5]
            tags = list(_extract_candidate_tags(str(text)))
            if not tags:
                continue
            cx = int((float(x0) + float(x1)) / 2)
            cy = int((float(y0) + float(y1)) / 2)
            for tag in tags:
                out[tag] = {"pos": [cx, cy], "confidence": 0.7, "source": "pdf_text"}
    finally:
        doc.close()
    return out


def _pickpoint_available() -> bool:
    # Cloud/headless envs often cannot open OpenCV windows.
    # If DISPLAY is absent, skip interactive fallback.
    import os

    return bool(os.environ.get("DISPLAY"))


def _estimate_missing_positions(
    out: Dict[str, Dict[str, object]],
    tags: set[str],
) -> Dict[str, Dict[str, object]]:
    """
    Fallback 3: estimate missing tags by compact clustering around existing positions.
    """
    missing = [t for t in sorted(tags) if t not in out]
    if not missing:
        return out
    if out:
        xs = [float(v["pos"][0]) for v in out.values()]
        ys = [float(v["pos"][1]) for v in out.values()]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
    else:
        cx = 1000.0
        cy = 1000.0

    step = 80.0
    for i, tag in enumerate(missing):
        dx = (i % 6) * step
        dy = (i // 6) * step
        out[tag] = {
            "pos": [int(cx + dx), int(cy + dy)],
            "confidence": 0.35,
            "source": "cluster_estimate",
        }
    return out


def detect_positions_with_confidence(
    plan_path: Path | None = None,
    allowed_tags: set[str] | None = None,
    pdf_source_path: Path | None = None,
) -> Dict[str, Dict[str, object]]:
    """
    Return position map with confidence:
      { "B200": {"pos":[x,y], "confidence":0.92, "source":"ocr"}, ... }
    """
    p = plan_path if plan_path is not None else default_plan_path()
    if not p.is_file():
        raise FileNotFoundError(f"Plan image not found: {p}")

    out: Dict[str, Dict[str, object]]
    try:
        out = _detect_with_easyocr(p)
    except Exception:
        out = {}

    allowed = set(allowed_tags) if allowed_tags is not None else None
    if allowed is not None:
        out = {k: v for k, v in out.items() if k in allowed}
    if out:
        if allowed is not None:
            return _estimate_missing_positions(out, allowed)
        return out

    # fallback 2: PDF text layer
    pdf_path = pdf_source_path
    if pdf_path is None and _is_pdf(p):
        pdf_path = p
    if pdf_path is not None and pdf_path.is_file():
        try:
            out = _detect_with_pdf_text_layer(pdf_path)
        except Exception:
            out = {}
        if allowed is not None:
            out = {k: v for k, v in out.items() if k in allowed}
        if out:
            if allowed is not None:
                return _estimate_missing_positions(out, allowed)
            return out

    # fallback 1: manual pickpoint (only if GUI available)
    if _pickpoint_available():
        try:
            picked = pick_points_on_plan(p)
            out = {
                str(k): {"pos": [int(v[0]), int(v[1])], "confidence": 0.85, "source": "pickpoint"}
                for k, v in picked.items()
            }
            if allowed is not None:
                out = {k: v for k, v in out.items() if k in allowed}
            if allowed is not None:
                return _estimate_missing_positions(out, allowed)
            return out
        except Exception:
            pass

    # fallback 3: clustering estimate only if allowed tags known
    if allowed is not None:
        return _estimate_missing_positions({}, allowed)
    raise RuntimeError("No positions detected and no fallback available.")


def detect_positions(
    plan_path: Path | None = None,
    allowed_tags: set[str] | None = None,
) -> Dict[str, Tuple[int, int]]:
    """
    Return tag center positions from plan image:
      { "B200": (x_px, y_px), "P001A": (x_px, y_px), ... }

    Strategy:
    1) OCR (easyocr) on plan image text
    2) If OCR fails / yields empty: fallback to manual pickpoint
    """
    rich = detect_positions_with_confidence(plan_path=plan_path, allowed_tags=allowed_tags)
    return {
        tag: (int(data["pos"][0]), int(data["pos"][1]))
        for tag, data in rich.items()
    }


def pixel_to_mm(
    positions_px: Dict[str, Tuple[int, int]],
    plan_path: Path | None = None,
    plan_width_mm: float = 17500.0,
) -> Dict[str, Tuple[float, float]]:
    """Convert pixel map to plan-mm map using plan width scale and image-bottom Y origin."""
    p = plan_path if plan_path is not None else default_plan_path()
    img = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read plan image: {p}")
    h, w = img.shape[:2]
    if w <= 0:
        raise ValueError(f"Invalid plan width: {w}")

    scale = float(plan_width_mm) / float(w)
    out: Dict[str, Tuple[float, float]] = {}
    for tag, (x, y) in positions_px.items():
        x_mm = float(x) * scale
        y_mm = float(h - y) * scale
        out[tag] = (x_mm, y_mm)
    return out
