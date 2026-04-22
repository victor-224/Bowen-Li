"""Phase 4: attach abstract 3D geometry labels (no mesh generation, no rendering)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def geometry_engine(scene: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map each equipment row to a simple geometry descriptor (non-rendered).

    Mutates a deep copy of scene so callers can keep an immutable snapshot if needed.
    """
    out = deepcopy(scene)
    equipment = out.get("equipment")
    if not isinstance(equipment, list):
        return out

    for e in equipment:
        if not isinstance(e, dict):
            continue
        svc = e.get("service")
        s = str(svc) if svc is not None else ""

        if "Tank" in s:
            e["geometry_type"] = "cylinder_vertical"
        elif "Exchanger" in s:
            e["geometry_type"] = "cylinder_horizontal"
        elif "Compressor" in s:
            e["geometry_type"] = "box"
        else:
            e["geometry_type"] = "cylinder"

    return out
