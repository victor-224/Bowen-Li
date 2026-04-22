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


def _wall_distance_mm(x: float, y: float, walls: List[Dict[str, Any]]) -> float:
    """
    Approximate min distance to any wall segment endpoint-projected distance in mm.
    Falls back to inf when walls are unavailable.
    """
    if not walls:
        return float("inf")
    best = float("inf")
    px, py = x, y
    for w in walls:
        if not isinstance(w, dict):
            continue
        p1 = w.get("p1")
        p2 = w.get("p2")
        if not (isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple)) and len(p1) >= 2 and len(p2) >= 2):
            continue
        x1, y1 = float(p1[0]), float(p1[1])
        x2, y2 = float(p2[0]), float(p2[1])
        dx = x2 - x1
        dy = y2 - y1
        denom = dx * dx + dy * dy
        if denom <= 0:
            dist = math.hypot(px - x1, py - y1)
        else:
            t = ((px - x1) * dx + (py - y1) * dy) / denom
            t = max(0.0, min(1.0, t))
            qx = x1 + t * dx
            qy = y1 + t * dy
            dist = math.hypot(px - qx, py - qy)
        if dist < best:
            best = dist
    return best


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
    walls = scene.get("walls")
    rooms = scene.get("rooms")
    if not isinstance(walls, list):
        walls = []
    if not isinstance(rooms, list):
        rooms = []

    for tag, (x, y) in coords.items():
        wall_dist = _wall_distance_mm(x, y, walls)
        if math.isfinite(wall_dist):
            near = wall_dist <= wall_margin_mm
        else:
            near = (
                (x - min_x) <= wall_margin_mm
                or (max_x - x) <= wall_margin_mm
                or (y - min_y) <= wall_margin_mm
                or (max_y - y) <= wall_margin_mm
            )
        relations[f"{tag}_near_wall"] = bool(near)
        in_center = False
        for room in rooms:
            if not isinstance(room, dict):
                continue
            c = room.get("center")
            if not (isinstance(c, (list, tuple)) and len(c) >= 2):
                continue
            cx, cy = float(c[0]), float(c[1])
            if math.hypot(x - cx, y - cy) <= wall_margin_mm:
                in_center = True
                break
        relations[f"{tag}_in_room_center"] = in_center

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

        za = a.get("zone_id")
        zb = b.get("zone_id")
        if za is not None and zb is not None:
            same_zone = str(za) == str(zb)
            relations[f"{ta}_in_same_zone_{tb}"] = same_zone
            relations[f"{tb}_in_same_zone_{ta}"] = same_zone

        # Basic process connectivity heuristics from service/type affinity.
        sa = str(a.get("service", "")).strip().lower()
        sb = str(b.get("service", "")).strip().lower()
        connected = False
        if sa and sb:
            tokens_a = set(sa.replace("/", " ").replace("-", " ").split())
            tokens_b = set(sb.replace("/", " ").replace("-", " ").split())
            connected = len(tokens_a.intersection(tokens_b)) > 0
        relations[f"{ta}_connected_process_{tb}"] = connected
        relations[f"{tb}_connected_process_{ta}"] = connected

        # Directional process hint: lower y as upstream baseline.
        relations[f"{ta}_upstream_{tb}"] = ay < by
        relations[f"{tb}_upstream_{ta}"] = by < ay
        relations[f"{ta}_downstream_{tb}"] = ay > by
        relations[f"{tb}_downstream_{ta}"] = by > ay

    return relations

