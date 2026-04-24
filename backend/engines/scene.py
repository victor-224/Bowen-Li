"""Assemble scene document from equipment + detected plan positions (canonical shape in scene_spec).

Scene stage MUST NOT access the filesystem directly. All runtime-asset
dependencies are governed by `backend/asset_contract.py`.
"""

from __future__ import annotations

import logging
import cv2
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from backend.api import equipment_dict_to_list
from backend.asset_contract import (
    PLAN_IMAGE_CONTRACT,
    AssetContractViolation,
    load_asset,
)
from backend.engines.geometry import geometry_engine
from backend.locator import detect_positions_with_confidence, pixel_to_mm
from backend.scene_spec import build_equipment_list, empty_scene
from backend.walls import parse_walls_and_rooms


logger = logging.getLogger("industrial_digital_twin.scene")

SCENE_STAGE = "scene_render"


def safe_load_image(path: str) -> Optional[Any]:
    """Safe image read used by degraded mode guard."""
    img = cv2.imread(path)
    if img is None:
        return None
    return img


def _degraded_empty_layout(
    equipment: Mapping[str, Mapping[str, Any]],
    warning: str = "missing_demo_asset",
) -> Dict[str, Any]:
    """Return a safe empty-layout scene that keeps downstream contracts stable."""
    rows = equipment_dict_to_list(equipment)
    items = build_equipment_list(rows, positions_mm={})
    scene: Dict[str, Any] = empty_scene({"layout": "empty", "warning": warning})
    scene["equipment"] = items
    scene["walls"] = []
    scene["rooms"] = []
    scene["center"] = [0.0, 0.0]
    return geometry_engine(scene)


def build_scene_document(
    equipment: Mapping[str, Mapping[str, Any]],
    plan_path: Optional[Path] = None,
    detected_positions: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """equipment (tag -> row) -> scene dict following backend/scene_spec.py.

    Position source priority: plan OCR/pickpoint -> mm conversion.
    The plan image asset is a contracted artifact; this stage only consumes
    it through the contract layer.
    """
    # Contract-governed input. Any violation surfaces as AssetContractViolation
    # which the API layer translates into a structured ASSET_* error.
    try:
        safe_plan = load_asset(PLAN_IMAGE_CONTRACT, stage=SCENE_STAGE, override_path=plan_path)
    except AssetContractViolation:
        logger.warning(
            "Layout image unavailable (demo or upload corrupted). Pipeline continues in degraded mode."
        )
        logger.warning(
            "Demo plan.png missing or corrupted, switching to empty layout mode"
        )
        return _degraded_empty_layout(equipment, warning="missing_demo_asset")
    if safe_load_image(str(safe_plan)) is None:
        logger.warning(
            "Layout image unavailable (demo or upload corrupted). Pipeline continues in degraded mode."
        )
        logger.warning(
            "Demo plan.png missing or corrupted, switching to empty layout mode"
        )
        return _degraded_empty_layout(equipment, warning="missing_demo_asset")

    allowed_tags = set(str(t) for t in equipment.keys())
    detected = (
        dict(detected_positions)
        if detected_positions is not None
        else detect_positions_with_confidence(plan_path=safe_plan, allowed_tags=allowed_tags)
    )
    pixel_positions: Dict[str, tuple[int, int]] = {}
    conf_map: Dict[str, float] = {}
    for tag, v in detected.items():
        if isinstance(v, dict):
            p = v.get("pos", [0, 0])
            pixel_positions[tag] = (int(p[0]), int(p[1]))
            conf_map[tag] = float(v.get("confidence", 0.0))
        else:
            pixel_positions[tag] = (int(v[0]), int(v[1]))
            conf_map[tag] = 0.7
    positions = pixel_to_mm(pixel_positions, safe_plan)
    rows = equipment_dict_to_list(equipment)
    items = build_equipment_list(rows, positions)
    wall_info = parse_walls_and_rooms(safe_plan)
    scene: Dict[str, Any] = empty_scene()
    for item in items:
        item["confidence"] = conf_map.get(str(item.get("tag", "")), 0.0)
    scene["equipment"] = items
    scene["walls"] = wall_info.get("walls", [])
    scene["rooms"] = wall_info.get("rooms", [])
    scene["center"] = wall_info.get("center", [0.0, 0.0])
    return geometry_engine(scene)


__all__ = ["build_scene_document", "AssetContractViolation", "SCENE_STAGE"]
