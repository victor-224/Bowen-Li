"""Assemble scene document from equipment dict + layout positions (canonical shape in scene_spec)."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from backend.api import equipment_dict_to_list
from backend.engines.geometry import geometry_engine
from backend.engines.layout import layout_engine
from backend.scene_spec import build_equipment_list, empty_scene


def build_scene_document(equipment: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """
    equipment (tag -> row) -> scene dict following backend/scene_spec.py.

    Layout positions come from layout_engine; structure and nesting are defined in scene_spec.
    """
    positions = layout_engine(equipment)
    rows = equipment_dict_to_list(equipment)
    items = build_equipment_list(rows, positions)
    scene: Dict[str, Any] = empty_scene()
    scene["equipment"] = items
    return geometry_engine(scene)
