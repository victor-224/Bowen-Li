"""Assemble scene document from equipment dict + layout + geometry labels."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from backend.api import equipment_dict_to_list
from backend.engines.geometry import geometry_engine
from backend.engines.layout import layout_engine


def build_scene_document(equipment: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """
    equipment (tag -> row) -> full scene dict with position_mm and geometry_type.

    Single source of truth for Flask /api/scene and main.run_engine_pipeline.
    """
    positions = layout_engine(equipment)
    rows = equipment_dict_to_list(equipment)
    items: list[Dict[str, Any]] = []
    for row in rows:
        tag = row["tag"]
        if tag not in positions:
            raise KeyError(f"layout_engine did not produce a position for tag {tag!r}")
        x, y = positions[tag]
        item = dict(row)
        item["position_mm"] = {"x": float(x), "y": float(y), "z": 0.0}
        items.append(item)

    scene: Dict[str, Any] = {
        "equipment": items,
        "walls": [],
        "meta": {"project": "Industrial Digital Twin"},
    }
    return geometry_engine(scene)
