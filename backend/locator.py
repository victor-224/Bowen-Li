"""Locate equipment tag positions from plan image (OCR-first, pickpoint fallback)."""

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


def _detect_with_easyocr(plan_path: Path) -> Dict[str, Tuple[int, int]]:
    import easyocr  # optional dependency, imported lazily

    reader = easyocr.Reader(["en"], gpu=False)
    results = reader.readtext(str(plan_path))
    out: Dict[str, Tuple[int, int]] = {}
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
                out[tag] = (cx, cy)
    return out


def _pickpoint_available() -> bool:
    # Cloud/headless envs often cannot open OpenCV windows.
    # If DISPLAY is absent, skip interactive fallback.
    import os

    return bool(os.environ.get("DISPLAY"))


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
    p = plan_path if plan_path is not None else default_plan_path()
    if not p.is_file():
        raise FileNotFoundError(f"Plan image not found: {p}")

    try:
        positions = _detect_with_easyocr(p)
    except Exception:
        positions = {}

    if allowed_tags is not None:
        positions = {k: v for k, v in positions.items() if k in allowed_tags}
    if positions:
        return positions

    # Fallback requested: manual click points on plan (only when GUI is available).
    if _pickpoint_available():
        try:
            picked = pick_points_on_plan(p)
            picked_map = {str(k): (int(v[0]), int(v[1])) for k, v in picked.items()}
            if allowed_tags is not None:
                return {k: v for k, v in picked_map.items() if k in allowed_tags}
            return picked_map
        except Exception:
            # In some environments DISPLAY exists but OpenCV HighGUI is unavailable.
            pass
    raise RuntimeError(
        "OCR did not detect any tag positions and interactive pickpoint fallback "
        "is unavailable in headless environment (DISPLAY not set)."
    )


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
