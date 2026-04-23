"""Assemble scene document from equipment + detected plan positions (canonical shape in scene_spec)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import cv2  # used for corruption pre-check

from backend.api import equipment_dict_to_list
from backend.engines.geometry import geometry_engine
from backend.locator import default_plan_path, detect_positions_with_confidence, pixel_to_mm
from backend.scene_spec import build_equipment_list, empty_scene
from backend.walls import parse_walls_and_rooms


logger = logging.getLogger("industrial_digital_twin.scene")


class ScenePlanMissingError(FileNotFoundError):
    """Raised when plan.png input is missing for scene build."""


class ScenePlanCorruptedError(ValueError):
    """Raised when plan.png input exists but is unreadable/corrupted."""


def _ensure_plan_asset(plan_path: Optional[Path]) -> Path:
    """Guard scene input asset: must exist and be readable by OpenCV."""
    if plan_path is None:
        plan_path = default_plan_path()
    p = Path(plan_path)
    if not p or not os.path.exists(p):
        raise ScenePlanMissingError(
            "[SCENE_ERROR] plan.png missing. Scene pipeline cannot proceed."
        )
    img = cv2.imread(str(p))
    if img is None:
        raise ScenePlanCorruptedError(
            "[SCENE_ERROR] plan.png is corrupted or unreadable"
        )
    logger.info("[SCENE] loading plan image: %s", str(p))
    return p


def build_scene_document(
    equipment: Mapping[str, Mapping[str, Any]],
    plan_path: Optional[Path] = None,
    detected_positions: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """equipment (tag -> row) -> scene dict following backend/scene_spec.py.

    Position source priority: plan OCR/pickpoint -> mm conversion.
    The plan image asset is required and must be readable before any OCR / parsing.
    """
    safe_plan = _ensure_plan_asset(plan_path)

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
