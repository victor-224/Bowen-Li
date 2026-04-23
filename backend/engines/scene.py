"""Assemble scene document from equipment + detected plan positions (canonical shape in scene_spec)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from backend.api import equipment_dict_to_list
from backend.engines.geometry import geometry_engine
from backend.locator import default_plan_path, detect_positions_with_confidence, pixel_to_mm
from backend.scene_spec import build_equipment_list, empty_scene
from backend.walls import parse_walls_and_rooms


def build_scene_document(
    equipment: Mapping[str, Mapping[str, Any]],
    plan_path: Optional[Path] = None,
    detected_positions: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    equipment (tag -> row) -> scene dict following backend/scene_spec.py.
    Position source priority: plan OCR/pickpoint -> mm conversion.
    """
    # Restrict locator to known equipment tags so no unrelated OCR text is used.
    allowed_tags = set(str(t) for t in equipment.keys())
    detected = (
        dict(detected_positions)
        if detected_positions is not None
        else detect_positions_with_confidence(plan_path=plan_path, allowed_tags=allowed_tags)
    )
    pixel_positions: Dict[str, tuple[int, int]] = {}
    conf_map: Dict[str, float] = {}
    for tag, v in detected.items():
        if isinstance(v, dict):
            p = v.get("pos", [0, 0])
            pixel_positions[tag] = (int(p[0]), int(p[1]))
            conf_map[tag] = float(v.get("confidence", 0.0))
        else:
            # backward compatibility with old locator output: {tag: (x, y)}
            pixel_positions[tag] = (int(v[0]), int(v[1]))
            conf_map[tag] = 0.7
    positions = pixel_to_mm(pixel_positions, plan_path)
    rows = equipment_dict_to_list(equipment)
    items = build_equipment_list(rows, positions)
    plan = plan_path if plan_path is not None else default_plan_path()
    wall_info = parse_walls_and_rooms(plan)
    scene: Dict[str, Any] = empty_scene()
    for item in items:
        item["confidence"] = conf_map.get(str(item.get("tag", "")), 0.0)
    scene["equipment"] = items
    scene["walls"] = wall_info.get("walls", [])
    scene["rooms"] = wall_info.get("rooms", [])
    scene["center"] = wall_info.get("center", [0.0, 0.0])
    return geometry_engine(scene)
