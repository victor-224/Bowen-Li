"""Assemble scene document from equipment + raw points using two-layer spatial flow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import cv2

from backend.api import equipment_dict_to_list
from backend.asset_contract import PLAN_IMAGE_CONTRACT, AssetContractViolation, load_asset
from backend.engines.geometry import geometry_engine
from backend.locator import detect_positions_with_confidence
from backend.opencv_util import opencv_imread_quiet
from backend.scene_spec import build_equipment_list, empty_scene
from backend.spatial.input import load_points
from backend.spatial.transform import pixel_to_world
from backend.walls import parse_walls_and_rooms


SCENE_STAGE = "scene_render"


def _degraded_empty_scene(
    equipment: Mapping[str, Mapping[str, Any]],
    reason: str,
) -> Dict[str, Any]:
    rows = equipment_dict_to_list(equipment)
    scene: Dict[str, Any] = empty_scene({"spatial_system": "two_layer_pixel_to_world"})
    scene["equipment"] = build_equipment_list(rows, {})
    scene["walls"] = []
    scene["rooms"] = []
    scene["center"] = [0.0, 0.0]
    scene.setdefault("meta", {})
    scene["meta"]["degraded"] = True
    scene["meta"]["degraded_reason"] = reason
    scene["meta"]["spatial_points_count"] = 0
    scene["meta"]["spatial_scene_allowed"] = False
    return geometry_engine(scene)


def _plan_shape(plan: Path) -> tuple[int, int]:
    with opencv_imread_quiet():
        img = cv2.imread(str(plan), cv2.IMREAD_COLOR)
    if img is None:
        raise AssetContractViolation(
            contract=PLAN_IMAGE_CONTRACT,
            code="ASSET_CORRUPTED",
            stage=SCENE_STAGE,
            message=f"Asset '{PLAN_IMAGE_CONTRACT.name}' is unreadable: {plan}",
        )
    h, w = img.shape[:2]
    return int(w), int(h)


def _estimate_drawing_roi(plan: Path) -> Optional[tuple[float, float, float, float]]:
    """
    Estimate the actual drawing area (exclude white margins/legend blocks).
    Returns normalized bbox (x0, y0, x1, y1) in [0,1], or None if unknown.
    """
    with opencv_imread_quiet():
        img = cv2.imread(str(plan), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    h, w = img.shape[:2]
    if w <= 0 or h <= 0:
        return None
    # Foreground = non-white drawing content.
    _, fg = cv2.threshold(img, 245, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel, iterations=2)
    points = cv2.findNonZero(fg)
    if points is None:
        return None
    x, y, bw, bh = cv2.boundingRect(points)
    if bw <= 0 or bh <= 0:
        return None
    area_ratio = (bw * bh) / float(w * h)
    if area_ratio < 0.05:
        return None
    # Slightly shrink ROI to avoid border text/noise.
    pad_x = max(2, int(0.01 * bw))
    pad_y = max(2, int(0.01 * bh))
    x0 = max(0, x + pad_x) / float(w)
    y0 = max(0, y + pad_y) / float(h)
    x1 = min(w, x + bw - pad_x) / float(w)
    y1 = min(h, y + bh - pad_y) / float(h)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def _filter_points_on_drawing(
    pixel_points: Mapping[str, tuple[float, float]],
    plan: Optional[Path],
    image_shape: tuple[int, int],
) -> tuple[Dict[str, tuple[float, float]], Dict[str, Any]]:
    """
    Keep only points likely inside real drawing area, dropping misleading legend tags
    (especially top-left label blocks unrelated to equipment placement).
    """
    out: Dict[str, tuple[float, float]] = {}
    diagnostics: Dict[str, Any] = {
        "roi": None,
        "raw_count": len(dict(pixel_points)),
        "kept_count": 0,
        "dropped_count": 0,
        "dropped_top_left_count": 0,
        "dropped_outside_roi_count": 0,
        "top_left_count_before": 0,
    }
    w, h = image_shape
    if w <= 0 or h <= 0:
        diagnostics["kept_count"] = len(dict(pixel_points))
        return dict(pixel_points), diagnostics

    roi = _estimate_drawing_roi(plan) if plan is not None else None
    diagnostics["roi"] = roi
    all_points = dict(pixel_points)
    top_left_candidates = set()
    for tag, (x, y) in all_points.items():
        xn = float(x) / float(w)
        yn = float(y) / float(h)
        if xn < 0.2 and yn < 0.2:
            top_left_candidates.add(str(tag))
    diagnostics["top_left_count_before"] = len(top_left_candidates)
    # Adaptive suppression:
    # only suppress top-left cluster when it dominates detections and there are
    # meaningful points elsewhere (typical legend/title-block pollution pattern).
    suppress_top_left = (
        len(top_left_candidates) >= 3
        and len(top_left_candidates) >= int(0.6 * max(1, len(all_points)))
        and (len(all_points) - len(top_left_candidates)) > 0
    )

    for tag, (x, y) in all_points.items():
        xn = float(x) / float(w)
        yn = float(y) / float(h)
        keep = True
        if roi is not None:
            x0, y0, x1, y1 = roi
            inside_roi = (x0 <= xn <= x1) and (y0 <= yn <= y1)
            if not inside_roi:
                keep = False
                diagnostics["dropped_outside_roi_count"] += 1
        if suppress_top_left and str(tag) in top_left_candidates:
            keep = False
            diagnostics["dropped_top_left_count"] += 1
        if keep:
            out[str(tag)] = (float(x), float(y))
    diagnostics["kept_count"] = len(out)
    diagnostics["dropped_count"] = diagnostics["raw_count"] - diagnostics["kept_count"]
    diagnostics["top_left_suppressed"] = bool(suppress_top_left)
    # Fail-open: if filtering wipes all detected points, keep raw points.
    # This avoids false-negative empty scenes due to over-strict ROI/corner rules.
    if diagnostics["raw_count"] > 0 and diagnostics["kept_count"] == 0:
        diagnostics["filter_fail_open"] = True
        diagnostics["kept_count"] = diagnostics["raw_count"]
        diagnostics["dropped_count"] = 0
        return dict(all_points), diagnostics
    diagnostics["filter_fail_open"] = False
    return out, diagnostics


def build_scene_document(
    equipment: Mapping[str, Mapping[str, Any]],
    plan_path: Optional[Path] = None,
    detected_positions: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if detected_positions is not None and plan_path is None:
        image_shape = (1920, 1080)
        safe_plan: Optional[Path] = None
    else:
        try:
            safe_plan = load_asset(PLAN_IMAGE_CONTRACT, stage=SCENE_STAGE, override_path=plan_path)
            image_shape = _plan_shape(safe_plan)
        except AssetContractViolation as exc:
            return _degraded_empty_scene(equipment, reason=str(exc))
    if detected_positions is None:
        raw_detected = detect_positions_with_confidence(
            plan_path=safe_plan,
            allowed_tags=set(str(t) for t in equipment.keys()),
        )
    else:
        raw_detected = dict(detected_positions)

    pixel_points = load_points(raw_detected)
    pixel_points, filter_diag = _filter_points_on_drawing(pixel_points, safe_plan, image_shape)
    world_points = pixel_to_world(pixel_points, image_shape, plan_width_mm=17500.0)

    rows = equipment_dict_to_list(equipment)
    # Only render 3D equipment that exists on the plan (has detected pixel/world point).
    rows_on_plan = [row for row in rows if str(row.get("tag", "")) in world_points]
    items = build_equipment_list(rows_on_plan, world_points)
    wall_info = parse_walls_and_rooms(safe_plan) if safe_plan is not None else {"walls": [], "rooms": [], "center": [0.0, 0.0]}

    scene: Dict[str, Any] = empty_scene({"spatial_system": "two_layer_pixel_to_world"})
    scene["equipment"] = items
    scene["walls"] = wall_info.get("walls", [])
    scene["rooms"] = wall_info.get("rooms", [])
    scene["center"] = wall_info.get("center", [0.0, 0.0])
    scene.setdefault("meta", {})
    scene["meta"]["spatial_points_count"] = len(world_points)
    scene["meta"]["spatial_scene_allowed"] = True
    scene["meta"]["spatial_raw_points_count"] = int(filter_diag.get("raw_count", 0))
    scene["meta"]["spatial_filtered_points_count"] = int(filter_diag.get("kept_count", len(world_points)))
    scene["meta"]["spatial_dropped_points_count"] = int(filter_diag.get("dropped_count", 0))
    scene["meta"]["spatial_filter_diagnostics"] = filter_diag
    return geometry_engine(scene)


__all__ = ["build_scene_document", "AssetContractViolation", "SCENE_STAGE"]
