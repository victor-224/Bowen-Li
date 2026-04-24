"""Spatial Authority Layer — single truth gate for layout-mm coordinates (scene input).

All other pipelines (normalizer, canonical, pixel_to_mm proposals) produce candidates only.
Scene geometry must consume only ``points`` from this module's output.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from backend.core.spatial_canonical_model import canonical_world_to_layout_mm
from backend.core.spatial_contract import SpatialMode


def _score_points(points: Mapping[str, Any]) -> float:
    if not isinstance(points, Mapping) or not points:
        return 0.0
    total = 0.0
    for v in points.values():
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            total += 1.0
        elif isinstance(v, Mapping):
            total += float(v.get("confidence", 0.5) or 0.0)
        else:
            total += 0.5
    return total


def _canonical_to_layout_mm(
    canonical_points: List[Mapping[str, Any]],
    *,
    image_shape: Tuple[int, int],
    plan_width_mm: float,
) -> Dict[str, Tuple[float, float]]:
    w, h = int(image_shape[0]), int(image_shape[1])
    if w <= 0:
        return {}
    scale = float(plan_width_mm) / float(w)
    out: Dict[str, Tuple[float, float]] = {}
    for row in canonical_points:
        if not isinstance(row, Mapping):
            continue
        tag = str(row.get("tag") or "").strip()
        if not tag:
            continue
        wv = row.get("world")
        if not isinstance(wv, (list, tuple)) or len(wv) < 2:
            continue
        wx, wy = float(wv[0]), float(wv[1])
        lx, ly = canonical_world_to_layout_mm(
            wx,
            wy,
            plan_width_mm=plan_width_mm,
            image_height_px=h,
            scale_mm_per_px=scale,
        )
        out[tag] = (lx, ly)
    return out


def _confidence_map_from_normalized(
    normalized: List[Mapping[str, Any]],
    tags: set[str],
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for row in normalized:
        if not isinstance(row, Mapping):
            continue
        tag = str(row.get("tag") or "").strip()
        if tag not in tags:
            continue
        out[tag] = float(row.get("confidence", 0.0) or 0.0)
    return out


def resolve_spatial_authority(
    *,
    canonical_points: List[Mapping[str, Any]],
    layout_mm_points: Mapping[str, Tuple[float, float]],
    cluster_points: Mapping[str, Tuple[float, float]],
    contract: Mapping[str, Any],
    allowed_tags: Optional[set[str]] = None,
    image_shape: Optional[Tuple[int, int]] = None,
    plan_width_mm: float = 17500.0,
    normalized_points: Optional[List[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Single truth gate. ``cluster_points`` never influences winner; only ``proposals_debug``.

    Returns keys: mode, points, rejected_sources, reason, confidence_map, proposals_debug
    (points values are [x_mm, y_mm] lists for JSON stability.)
    """
    c = dict(contract) if isinstance(contract, Mapping) else {}
    spatial_mode = str(c.get("spatial_mode") or SpatialMode.DEGRADED).upper()
    scene_allowed = bool(c.get("scene_allowed"))

    layout: Dict[str, Tuple[float, float]] = {
        str(k): (float(v[0]), float(v[1]))
        for k, v in (layout_mm_points or {}).items()
        if isinstance(v, (list, tuple)) and len(v) >= 2
    }
    cluster: Dict[str, Tuple[float, float]] = {
        str(k): (float(v[0]), float(v[1]))
        for k, v in (cluster_points or {}).items()
        if isinstance(v, (list, tuple)) and len(v) >= 2
    }

    canonical_layout: Dict[str, Tuple[float, float]] = {}
    if image_shape is not None and canonical_points:
        canonical_layout = _canonical_to_layout_mm(
            list(canonical_points),
            image_shape=image_shape,
            plan_width_mm=plan_width_mm,
        )

    # Winner scoring: canonical vs layout only — cluster never participates.
    scores = {
        "canonical": _score_points(canonical_layout),
        "layout": _score_points(layout),
    }

    proposals_debug: Dict[str, Any] = {"cluster_estimate": dict(cluster)}

    def _no_spatial(reason: str, rejected: List[str]) -> Dict[str, Any]:
        return {
            "mode": "NO_SPATIAL",
            "points": {},
            "rejected_sources": rejected,
            "reason": reason,
            "confidence_map": {},
            "proposals_debug": proposals_debug,
        }

    if not scene_allowed or spatial_mode == SpatialMode.VISUAL_ONLY:
        rej = ["cluster_estimate", "canonical_chain", "layout_mm_proposal"]
        if cluster:
            rej.append("cluster_proposals_only_debug")
        return _no_spatial("contract disallows scene geometry", rej)

    winner: Optional[str] = None
    if spatial_mode == SpatialMode.REAL:
        winner = "canonical" if scores["canonical"] > 0 else "layout"
    elif spatial_mode == SpatialMode.DEGRADED:
        if scores["layout"] > 0:
            winner = "layout"
        elif scores["canonical"] > 0:
            winner = "canonical"
        else:
            winner = None
    else:
        winner = "canonical" if scores["canonical"] > 0 else ("layout" if scores["layout"] > 0 else None)

    if winner is None or scores.get(winner, 0) <= 0:
        return _no_spatial(
            "no trusted spatial source",
            ["canonical_chain", "layout_mm_proposal", "cluster_estimate_debug_only"],
        )

    src = dict(canonical_layout) if winner == "canonical" else dict(layout)
    tags = allowed_tags if allowed_tags is not None else set(src.keys())

    rejected_sources: List[str] = ["cluster_estimate"]
    if cluster:
        rejected_sources.append("cluster_geometry_forbidden")
    if winner == "canonical" and scores["layout"] > 0:
        rejected_sources.append("layout_mm_not_authoritative")
    if winner == "layout" and scores["canonical"] > 0:
        rejected_sources.append("canonical_chain_not_authoritative")

    points: Dict[str, List[float]] = {}
    for tag in tags:
        if tag in src:
            x, y = src[tag]
            points[tag] = [round(float(x), 6), round(float(y), 6)]
        else:
            points[tag] = [0.0, 0.0]

    norm = list(normalized_points) if normalized_points else []
    confidence_map = _confidence_map_from_normalized(norm, tags)

    return {
        "mode": "FINAL",
        "points": points,
        "rejected_sources": rejected_sources,
        "reason": f"authority_winner={winner}",
        "confidence_map": confidence_map,
        "proposals_debug": proposals_debug,
    }


__all__ = ["resolve_spatial_authority"]
