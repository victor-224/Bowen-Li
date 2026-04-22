"""Industrial layout semantic graph builder."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Tuple


def _xy_from_node(n: Mapping[str, Any]) -> Tuple[float, float]:
    p = n.get("position_mm")
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return float(p[0]), float(p[1])
    if isinstance(p, dict):
        return float(p.get("x", 0.0)), float(p.get("y", 0.0))
    return 0.0, 0.0


def _service_zone_type(service: str) -> str:
    s = (service or "").lower()
    if any(k in s for k in ("utility", "steam", "air", "water", "nitrogen", "instrument")):
        return "utility_area"
    if any(k in s for k in ("storage", "tank", "drum", "buffer")):
        return "storage_area"
    if any(k in s for k in ("rack", "pipe", "header", "manifold")):
        return "pipe_rack_zone"
    if any(k in s for k in ("maintenance", "corridor", "access", "walkway")):
        return "maintenance_corridor"
    return "process_unit"


def _equipment_type(node: Mapping[str, Any]) -> str:
    gt = str(node.get("geometry_type", "")).lower()
    svc = str(node.get("service", "")).lower()
    if "pump" in svc:
        return "pump"
    if "tank" in svc or "drum" in svc:
        return "tank"
    if "exchanger" in svc or "cooler" in svc or "heater" in svc:
        return "exchanger"
    if "compressor" in svc:
        return "compressor"
    if "box" in gt:
        return "box_equipment"
    if "cylinder" in gt:
        return "cylindrical_equipment"
    return "equipment"


def _process_role(node: Mapping[str, Any]) -> str:
    svc = str(node.get("service", "")).lower()
    if "feed" in svc:
        return "feed"
    if "storage" in svc or "tank" in svc:
        return "storage"
    if "pump" in svc:
        return "transfer"
    if "compressor" in svc:
        return "compression"
    if "cooler" in svc or "heater" in svc or "exchanger" in svc:
        return "thermal_exchange"
    return "process"


def _dist(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    ax, ay = _xy_from_node(a)
    bx, by = _xy_from_node(b)
    return math.hypot(ax - bx, ay - by)


def _cluster_nodes(nodes: List[Dict[str, Any]], threshold_mm: float = 12000.0) -> List[List[Dict[str, Any]]]:
    """Simple distance-based connected-components clustering."""
    n = len(nodes)
    visited = [False] * n
    groups: List[List[Dict[str, Any]]] = []

    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if _dist(nodes[i], nodes[j]) <= threshold_mm:
                adj[i].append(j)
                adj[j].append(i)

    for i in range(n):
        if visited[i]:
            continue
        stack = [i]
        visited[i] = True
        comp: List[Dict[str, Any]] = []
        while stack:
            cur = stack.pop()
            comp.append(nodes[cur])
            for nb in adj[cur]:
                if not visited[nb]:
                    visited[nb] = True
                    stack.append(nb)
        groups.append(comp)
    return groups


def _zone_from_cluster(zone_id: str, cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
    cx = sum(_xy_from_node(n)[0] for n in cluster) / max(len(cluster), 1)
    cy = sum(_xy_from_node(n)[1] for n in cluster) / max(len(cluster), 1)
    services = [str(n.get("service", "")) for n in cluster]
    zone_type = _service_zone_type(max(services, key=lambda s: len(s)) if services else "")
    return {
        "zone_id": zone_id,
        "type": zone_type,
        "devices": [str(n.get("tag")) for n in cluster if n.get("tag")],
        "center": [round(cx, 3), round(cy, 3)],
    }


def _edge_confidence(
    source: Dict[str, Any],
    target: Dict[str, Any],
    base: float,
) -> float:
    ca = float(source.get("confidence", 0.5))
    cb = float(target.get("confidence", 0.5))
    return round(max(0.05, min(1.0, base * ((ca + cb) / 2.0))), 3)


def _build_space_edges(nodes: List[Dict[str, Any]], relations: Mapping[str, Any], zone_by_tag: Mapping[str, str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    by_tag = {str(n.get("tag")): n for n in nodes if n.get("tag")}
    tags = sorted(by_tag.keys())
    for i, a in enumerate(tags):
        for b in tags[i + 1 :]:
            ka = f"distance_{a}_{b}"
            kb = f"distance_{b}_{a}"
            dist_m = relations.get(ka, relations.get(kb))
            if isinstance(dist_m, (int, float)):
                out.append(
                    {
                        "source": a,
                        "target": b,
                        "type": "distance",
                        "value": float(dist_m),
                        "confidence": _edge_confidence(by_tag[a], by_tag[b], 0.9),
                    }
                )
            lkey = f"{a}_left_of_{b}"
            if relations.get(lkey) is True:
                out.append(
                    {
                        "source": a,
                        "target": b,
                        "type": "left_of",
                        "confidence": _edge_confidence(by_tag[a], by_tag[b], 0.85),
                    }
                )
            rkey = f"{b}_left_of_{a}"
            if relations.get(rkey) is True:
                out.append(
                    {
                        "source": b,
                        "target": a,
                        "type": "left_of",
                        "confidence": _edge_confidence(by_tag[a], by_tag[b], 0.85),
                    }
                )
            if zone_by_tag.get(a) and zone_by_tag.get(a) == zone_by_tag.get(b):
                out.append(
                    {
                        "source": a,
                        "target": b,
                        "type": "in_same_zone",
                        "zone_id": zone_by_tag[a],
                        "confidence": _edge_confidence(by_tag[a], by_tag[b], 0.95),
                    }
                )
    return out


def _build_process_edges(nodes: List[Dict[str, Any]], zone_by_tag: Mapping[str, str]) -> List[Dict[str, Any]]:
    """Process flow inference by role + X ordering within each zone."""
    zone_nodes: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        tag = str(n.get("tag", ""))
        zid = zone_by_tag.get(tag)
        if zid:
            zone_nodes[zid].append(n)

    edges: List[Dict[str, Any]] = []
    for zid, items in zone_nodes.items():
        role_rank = {
            "feed": 0,
            "transfer": 1,
            "compression": 2,
            "thermal_exchange": 3,
            "storage": 4,
            "process": 5,
        }
        ordered = sorted(
            items,
            key=lambda n: (role_rank.get(str(n.get("process_role", "process")), 99), _xy_from_node(n)[0]),
        )
        for i in range(len(ordered) - 1):
            a = str(ordered[i].get("tag"))
            b = str(ordered[i + 1].get("tag"))
            if a and b:
                base_conf = _edge_confidence(ordered[i], ordered[i + 1], 0.8)
                edges.append({"source": a, "target": b, "type": "upstream", "confidence": base_conf})
                edges.append({"source": b, "target": a, "type": "downstream", "confidence": base_conf})
                edges.append(
                    {
                        "source": a,
                        "target": b,
                        "type": "connected_process",
                        "zone_id": zid,
                        "confidence": base_conf,
                    }
                )
    return edges


def _build_constraints(zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for z in zones:
        out.append(
            {
                "type": "zone_capacity",
                "zone_id": z["zone_id"],
                "max_devices": max(4, len(z.get("devices", [])) + 2),
            }
        )
        out.append(
            {
                "type": "safety_clearance",
                "zone_id": z["zone_id"],
                "min_distance_m": 2.0,
            }
        )
    return out


def build_layout_graph(
    scene: Mapping[str, Any],
    walls: Mapping[str, Any],
    relations: Mapping[str, Any],
    excel_data: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """
    Build industrial semantic graph:
    {
      nodes: [...],
      edges: [...],
      zones: [...],
      constraints: [...]
    }
    """
    src_nodes = scene.get("equipment", [])
    nodes: List[Dict[str, Any]] = []
    if isinstance(src_nodes, list):
        for e in src_nodes:
            if not isinstance(e, dict) or not e.get("tag"):
                continue
            tag = str(e["tag"])
            attrs = excel_data.get(tag, {})
            n = dict(e)
            n["equipment_type"] = _equipment_type(e)
            n["service_system"] = str(attrs.get("service", e.get("service", "")))
            n["process_role"] = _process_role(e)
            conf = e.get("position_confidence")
            n["confidence"] = float(conf) if isinstance(conf, (int, float)) else 0.5
            nodes.append(n)

    clusters = _cluster_nodes(nodes)
    zones: List[Dict[str, Any]] = []
    zone_by_tag: Dict[str, str] = {}
    for i, c in enumerate(clusters, start=1):
        z = _zone_from_cluster(f"Z{i}", c)
        zones.append(z)
        for t in z["devices"]:
            zone_by_tag[t] = z["zone_id"]

    for n in nodes:
        t = str(n.get("tag", ""))
        if t in zone_by_tag:
            n["zone_id"] = zone_by_tag[t]

    edges = _build_space_edges(nodes, relations, zone_by_tag)
    edges.extend(_build_process_edges(nodes, zone_by_tag))
    constraints = _build_constraints(zones)

    walls_out: Dict[str, Any]
    if isinstance(walls, dict):
        walls_out = dict(walls)
    else:
        walls_out = {"walls": list(walls) if isinstance(walls, list) else []}

    return {
        "nodes": nodes,
        "edges": edges,
        "zones": zones,
        "constraints": constraints,
        "walls": walls_out,
    }
