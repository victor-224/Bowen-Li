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
) -> Dict[str, tuple[float, float]]:
    """
    Keep only points likely inside real drawing area, dropping misleading legend tags
    (especially top-left label blocks unrelated to equipment placement).
    """
    out: Dict[str, tuple[float, float]] = {}
    w, h = image_shape
    if w <= 0 or h <= 0:
        return dict(pixel_points)

    roi = _estimate_drawing_roi(plan) if plan is not None else None
    for tag, (x, y) in dict(pixel_points).items():
        xn = float(x) / float(w)
        yn = float(y) / float(h)
        keep = True
        if roi is not None:
            x0, y0, x1, y1 = roi
            keep = (x0 <= xn <= x1) and (y0 <= yn <= y1)
        # Hard guard for common misleading corner labels.
        if xn < 0.2 and yn < 0.2:
            keep = False
        if keep:
            out[str(tag)] = (float(x), float(y))
    return out


def build_scene_document(
    equipment: Mapping[str, Mapping[str, Any]],
    plan_path: Optional[Path] = None,
    detected_positions: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if detected_positions is not None and plan_path is None:
        image_shape = (1920, 1080)
        safe_plan: Optional[Path] = None
    else:
        safe_plan = load_asset(PLAN_IMAGE_CONTRACT, stage=SCENE_STAGE, override_path=plan_path)
        image_shape = _plan_shape(safe_plan)
    if detected_positions is None:
        raw_detected = detect_positions_with_confidence(
            plan_path=safe_plan,
            allowed_tags=set(str(t) for t in equipment.keys()),
        )
    else:
        raw_detected = dict(detected_positions)

    pixel_points = load_points(raw_detected)
    pixel_points = _filter_points_on_drawing(pixel_points, safe_plan, image_shape)
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
    return geometry_engine(scene)


__all__ = ["build_scene_document", "AssetContractViolation", "SCENE_STAGE"]
