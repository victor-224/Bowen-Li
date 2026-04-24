"""Locate equipment tag positions with confidence and fallback chain."""

from __future__ import annotations

import logging
import re
import json
import warnings
from pathlib import Path
from typing import Dict, Iterable, Tuple

import cv2

from backend.core.spatial_contract import (
    SpatialMode,
    build_spatial_integrity_contract,
)
from backend.core.spatial_truth_ledger import log_spatial_event
from backend.pickpoint import pick_points_on_plan
from backend.opencv_util import opencv_imread_quiet
from backend.core.spatial_frame import pixel_to_layout_mm

_TAG_PATTERN = re.compile(r"[A-Z]\s*\d{2,4}\s*[A-Z]?", re.IGNORECASE)
logger = logging.getLogger("industrial_digital_twin.spatial_debug")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_plan_path() -> Path:
    runtime_plan = _repo_root() / "data" / "runtime" / "plan.png"
    if runtime_plan.is_file():
        with opencv_imread_quiet():
            img = cv2.imread(str(runtime_plan), cv2.IMREAD_COLOR)
        if img is not None:
            return runtime_plan
    default_plan = _repo_root() / "data" / "plan_hd.png"
    if default_plan.is_file():
        return default_plan
    if runtime_plan.is_file():
        return runtime_plan
    return default_plan


def _cache_path() -> Path:
    return _repo_root() / "data" / "runtime" / "positions_cache.json"


def _normalize_tag(text: str) -> str:
    return "".join(text.upper().split())


def _extract_candidate_tags(text: str) -> Iterable[str]:
    for m in _TAG_PATTERN.finditer(text or ""):
        t = _normalize_tag(m.group(0))
        if t:
            yield t


def _is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def _gpu_available_for_ocr() -> bool:
    # Operator override for forcing CPU mode even when CUDA is present.
    if str(__import__("os").environ.get("FORCE_OCR_CPU", "")).strip().lower() in {"1", "true", "yes"}:
        return False
    try:
        import torch  # optional dependency from easyocr stack

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _detect_with_easyocr(plan_path: Path) -> Dict[str, Dict[str, object]]:
    import easyocr  # optional dependency, imported lazily

    # Silence non-actionable CPU-only warnings in headless/cloud environments.
    use_gpu = _gpu_available_for_ocr()
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*pin_memory.*no accelerator is found.*",
            category=UserWarning,
        )
        reader = easyocr.Reader(["en"], gpu=use_gpu, verbose=False)
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


def _merge_votes(
    a: Dict[str, Dict[str, object]],
    b: Dict[str, Dict[str, object]],
) -> Dict[str, Dict[str, object]]:
    """
    Multi-model vote merge:
    - If same tag appears in both detectors, average position and increase confidence.
    - Otherwise keep single-source candidate.
    """
    out: Dict[str, Dict[str, object]] = {}
    tags = set(a.keys()) | set(b.keys())
    for t in tags:
        va = a.get(t)
        vb = b.get(t)
        if va and vb:
            xa, ya = va["pos"]  # type: ignore[index]
            xb, yb = vb["pos"]  # type: ignore[index]
            ca = float(va.get("confidence", 0.0))
            cb = float(vb.get("confidence", 0.0))
            out[t] = {
                "pos": [int((float(xa) + float(xb)) / 2.0), int((float(ya) + float(yb)) / 2.0)],
                "confidence": min(1.0, (ca + cb) / 2.0 + 0.1),
                "source": "ocr_vote",
            }
        elif va:
            out[t] = dict(va)
        elif vb:
            out[t] = dict(vb)
    return out


def _load_cached_positions() -> Dict[str, Dict[str, object]]:
    p = _cache_path()
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: Dict[str, Dict[str, object]] = {}
    if isinstance(raw, dict):
        for tag, v in raw.items():
            if isinstance(v, dict) and "pos" in v:
                pos = v.get("pos")
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    out[str(tag)] = {
                        "pos": [int(pos[0]), int(pos[1])],
                        "confidence": float(v.get("confidence", 0.25)),
                        "source": "cache",
                    }
    return out


def _save_cached_positions(positions: Dict[str, Dict[str, object]]) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(positions, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


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
        ocr_out = _detect_with_easyocr(p)
    except Exception:
        ocr_out = {}

    pdf_out: Dict[str, Dict[str, object]] = {}
    pdf_path = pdf_source_path
    if pdf_path is None and _is_pdf(p):
        pdf_path = p
    if pdf_path is not None and pdf_path.is_file():
        try:
            pdf_out = _detect_with_pdf_text_layer(pdf_path)
        except Exception:
            pdf_out = {}

    out = _merge_votes(ocr_out, pdf_out)
    allowed = set(allowed_tags) if allowed_tags is not None else None
    if allowed is not None:
        out = {k: v for k, v in out.items() if k in allowed}
    if out:
        if allowed is not None:
            # Keep REAL source points only. Missing tags can be estimated for
            # preview usage, but must be explicitly tagged as visual-only.
            merged = _estimate_missing_positions(dict(out), allowed)
            for v in merged.values():
                if isinstance(v, dict) and str(v.get("source")) == "cluster_estimate":
                    v["visual_only"] = True
            return merged
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
                out = _estimate_missing_positions(out, allowed)
                for v in out.values():
                    if isinstance(v, dict) and str(v.get("source")) == "cluster_estimate":
                        v["visual_only"] = True
            _save_cached_positions(out)
            return out
        except Exception:
            pass

    # fallback 2: cache reuse
    cached = _load_cached_positions()
    if allowed is not None:
        cached = {k: v for k, v in cached.items() if k in allowed}
    if cached:
        if allowed is not None:
            merged = _estimate_missing_positions(cached, allowed)
            for v in merged.values():
                if isinstance(v, dict) and str(v.get("source")) == "cluster_estimate":
                    v["visual_only"] = True
            return merged
        return cached

    # fallback 3: clustering estimate only if allowed tags known
    if allowed is not None:
        estimated = _estimate_missing_positions({}, allowed)
        for v in estimated.values():
            if isinstance(v, dict):
                v["visual_only"] = True
        _save_cached_positions(estimated)
        return estimated
    raise RuntimeError("No positions detected and no fallback available.")


def resolve_spatial_positions_with_contract(
    plan_path: Path | None = None,
    allowed_tags: set[str] | None = None,
    pdf_source_path: Path | None = None,
) -> Dict[str, object]:
    """
    Resolve positions + authoritative SpatialIntegrityContract in one place.

    Returns:
      {
        "positions": {tag -> {"pos":[x,y], "confidence", "source", ...}},
        "spatial_contract": {...}
      }
    """
    p = plan_path if plan_path is not None else default_plan_path()
    positions: Dict[str, Dict[str, object]] = {}
    reason = ""
    source = "none"

    # Plan readability gate for REAL mode.
    plan_readable = False
    if p.is_file():
        try:
            with opencv_imread_quiet():
                plan_readable = cv2.imread(str(p), cv2.IMREAD_COLOR) is not None
        except Exception:  # noqa: BLE001
            plan_readable = False

    try:
        positions = detect_positions_with_confidence(
            plan_path=p, allowed_tags=allowed_tags, pdf_source_path=pdf_source_path
        )
    except Exception as e:  # noqa: BLE001
        positions = {}
        reason = str(e)

    if positions:
        # Prefer the dominant source among returned tags.
        src_count: Dict[str, int] = {}
        has_visual_only = False
        for v in positions.values():
            if not isinstance(v, dict):
                continue
            s = str(v.get("source") or "unknown")
            src_count[s] = src_count.get(s, 0) + 1
            has_visual_only = has_visual_only or bool(v.get("visual_only", False))
        source = max(src_count.items(), key=lambda x: x[1])[0] if src_count else "unknown"
        if source == "cluster_estimate" or has_visual_only:
            contract = build_spatial_integrity_contract(
                spatial_valid=False,
                spatial_mode=SpatialMode.VISUAL_ONLY,
                source=source,
                scene_allowed=False,
                visual_allowed=True,
                reason=reason or "synthetic fallback coordinates",
            )
        elif source in {"ocr", "pdf_text", "ocr_vote", "pickpoint"}:
            contract = build_spatial_integrity_contract(
                spatial_valid=True,
                spatial_mode=SpatialMode.REAL,
                source=source,
                scene_allowed=True,
                visual_allowed=True,
                reason=reason,
            )
        else:
            contract = build_spatial_integrity_contract(
                spatial_valid=plan_readable,
                spatial_mode=SpatialMode.REAL if plan_readable else SpatialMode.DEGRADED,
                source=source,
                scene_allowed=bool(plan_readable),
                visual_allowed=True,
                reason=reason or ("unknown source but plan unreadable" if not plan_readable else ""),
            )
    else:
        contract = build_spatial_integrity_contract(
            spatial_valid=False,
            spatial_mode=SpatialMode.DEGRADED,
            source="none",
            scene_allowed=False,
            visual_allowed=True,
            reason=reason or ("plan unreadable" if not plan_readable else "empty detection"),
        )

    log_spatial_event(
        {
            "stage": "locator",
            "source": source,
            "contract_mode": contract.get("spatial_mode", SpatialMode.DEGRADED),
            "scene_allowed": bool(contract.get("scene_allowed", False)),
            "used_in_scene": False,
            "bypass_detected": False,
            "reason": contract.get("reason") or reason or "locator_contract_resolved",
        }
    )

    return {"positions": positions, "spatial_contract": contract}


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
    with opencv_imread_quiet():
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read plan image: {p}")
    h, w = img.shape[:2]
    if w <= 0:
        raise ValueError(f"Invalid plan width: {w}")

    out: Dict[str, Tuple[float, float]] = {}
    for tag, (x, y) in positions_px.items():
        out[tag] = pixel_to_layout_mm(float(x), float(y), w, h, plan_width_mm)
    return out
