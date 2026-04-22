"""Phase 4: ensure geometry_type labels (non-rendered); canonical rules live in scene_spec."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from backend.scene_spec import infer_geometry_type


def geometry_engine(scene: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure each equipment item has geometry_type using scene_spec inference when missing.

    Does not create meshes or modify dimensions.
    """
    out = deepcopy(scene)
    equipment = out.get("equipment")
    if not isinstance(equipment, list):
        return out

    for e in equipment:
        if not isinstance(e, dict):
            continue
        if not e.get("geometry_type"):
            e["geometry_type"] = infer_geometry_type(e.get("service"))

    return out
