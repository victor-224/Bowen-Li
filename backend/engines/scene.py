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
