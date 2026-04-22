"""Phase 3: basic pairwise distance check in the plan (x, y) plane."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence


def _xy_mm(position_mm: Any) -> tuple[float, float]:
    if position_mm is None:
        return (0.0, 0.0)
    if isinstance(position_mm, (list, tuple)) and len(position_mm) >= 2:
        return (float(position_mm[0]), float(position_mm[1]))
    if isinstance(position_mm, dict):
        return (float(position_mm.get("x", 0)), float(position_mm.get("y", 0)))
    raise TypeError(f"position_mm must be sequence or dict, got {type(position_mm)!r}")


def collision_engine(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Basic collision / clearance check:
    - compare centers in the XY plane (mm)
    - flag pairs closer than min_distance (mm)
    """
    min_distance = 2000.0
    collisions: List[Dict[str, Any]] = []

    equipment = scene.get("equipment")
    if not isinstance(equipment, list):
        return collisions

    n = len(equipment)
    for i in range(n):
        for j in range(i + 1, n):
            a = equipment[i]
            b = equipment[j]
            if not isinstance(a, dict) or not isinstance(b, dict):
                continue
            pa = _xy_mm(a.get("position_mm"))
            pb = _xy_mm(b.get("position_mm"))

            dist = ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5

            if dist < min_distance:
                collisions.append(
                    {
                        "a": a.get("tag"),
                        "b": b.get("tag"),
                        "distance": dist,
                    }
                )

    return collisions
