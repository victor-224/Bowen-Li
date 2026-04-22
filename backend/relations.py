"""Industrial spatial relations engine (basic rule-based implementation)."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


def _xy_mm(item: Dict[str, Any]) -> Tuple[float, float]:
    p = item.get("position_mm")
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return float(p[0]), float(p[1])
    if isinstance(p, dict):
        return float(p.get("x", 0.0)), float(p.get("y", 0.0))
    return 0.0, 0.0


def _pairs(equipment: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    out: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    n = len(equipment)
    for i in range(n):
        for j in range(i + 1, n):
            out.append((equipment[i], equipment[j]))
    return out


def _is_parallel(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """
    Basic parallel rule:
    - same declared orientation in 'position' field (H/V), or
    - same geometry type.
    """
    pa = str(a.get("position", "")).strip().upper()
    pb = str(b.get("position", "")).strip().upper()
    if pa in {"H", "V"} and pb in {"H", "V"}:
        return pa == pb
    return str(a.get("geometry_type", "")) == str(b.get("geometry_type", ""))


def build_relations(scene: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute basic industrial spatial relations from scene equipment:
    1) left/right
    2) up/down
    3) euclidean distance (meters)
    4) near-wall detection
    5) parallel relation
    """
    relations: Dict[str, Any] = {}
    equipment = scene.get("equipment", [])
    if not isinstance(equipment, list):
        return relations

    valid_eq = [e for e in equipment if isinstance(e, dict) and e.get("tag")]
    if not valid_eq:
        return relations

    coords = {str(e["tag"]): _xy_mm(e) for e in valid_eq}
    xs = [xy[0] for xy in coords.values()]
    ys = [xy[1] for xy in coords.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    wall_margin_mm = 2000.0

    for tag, (x, y) in coords.items():
        near = (
            (x - min_x) <= wall_margin_mm
            or (max_x - x) <= wall_margin_mm
            or (y - min_y) <= wall_margin_mm
            or (max_y - y) <= wall_margin_mm
        )
        relations[f"{tag}_near_wall"] = bool(near)

    for a, b in _pairs(valid_eq):
        ta = str(a["tag"])
        tb = str(b["tag"])
        ax, ay = coords[ta]
        bx, by = coords[tb]

        relations[f"{ta}_left_of_{tb}"] = ax < bx
        relations[f"{tb}_left_of_{ta}"] = bx < ax
        relations[f"{ta}_above_{tb}"] = ay > by
        relations[f"{tb}_above_{ta}"] = by > ay

        dist_m = math.hypot(ax - bx, ay - by) / 1000.0
        relations[f"distance_{ta}_{tb}"] = round(dist_m, 3)

        is_parallel = _is_parallel(a, b)
        relations[f"{ta}_parallel_{tb}"] = is_parallel
        relations[f"{tb}_parallel_{ta}"] = is_parallel

    return relations

