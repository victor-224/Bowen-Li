"""Phase C: topology constraint optimization helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple


def _node_xy(node: Mapping[str, Any]) -> Tuple[float, float]:
    pos = node.get("position_mm")
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        return float(pos[0]), float(pos[1])
    return 0.0, 0.0


def optimize_topology(layout_graph: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Produce machine-calculable topology diagnostics:
    - spacing violations against safety_clearance constraints
    - overloaded zones against zone_capacity constraints
    - candidate edge reroutes (advisory)
    """
    nodes = [n for n in layout_graph.get("nodes", []) if isinstance(n, dict) and n.get("tag")]
    constraints = [c for c in layout_graph.get("constraints", []) if isinstance(c, dict)]
    zone_cap = {str(c.get("zone_id")): int(c.get("max_devices", 0)) for c in constraints if c.get("type") == "zone_capacity"}
    zone_clearance = {
        str(c.get("zone_id")): float(c.get("min_distance_m", 2.0)) for c in constraints if c.get("type") == "safety_clearance"
    }

    by_zone: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes:
        z = str(n.get("zone_id", ""))
        by_zone.setdefault(z, []).append(n)

    overloaded_zones: List[Dict[str, Any]] = []
    for zid, members in by_zone.items():
        cap = zone_cap.get(zid)
        if cap and len(members) > cap:
            overloaded_zones.append({"zone_id": zid, "devices": len(members), "max_devices": cap, "overflow": len(members) - cap})

    spacing_violations: List[Dict[str, Any]] = []
    for zid, members in by_zone.items():
        min_m = zone_clearance.get(zid, 2.0)
        min_mm = min_m * 1000.0
        for i in range(len(members)):
            ax, ay = _node_xy(members[i])
            at = str(members[i].get("tag"))
            for j in range(i + 1, len(members)):
                bx, by = _node_xy(members[j])
                bt = str(members[j].get("tag"))
                d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                if d < min_mm:
                    spacing_violations.append(
                        {
                            "zone_id": zid,
                            "a": at,
                            "b": bt,
                            "distance_m": round(d / 1000.0, 3),
                            "required_min_m": round(min_m, 3),
                        }
                    )

    reroute_hints: List[Dict[str, Any]] = []
    for issue in spacing_violations[:50]:
        reroute_hints.append(
            {
                "action": "separate_pair",
                "zone_id": issue["zone_id"],
                "pair": [issue["a"], issue["b"]],
                "reason": "safety_clearance_violation",
            }
        )

    score = max(0.0, 1.0 - min(0.9, (len(spacing_violations) * 0.04 + len(overloaded_zones) * 0.1)))
    return {
        "health_score": round(score, 3),
        "spacing_violations": spacing_violations,
        "overloaded_zones": overloaded_zones,
        "reroute_hints": reroute_hints,
    }
