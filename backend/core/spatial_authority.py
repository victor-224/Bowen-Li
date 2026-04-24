"""Spatial Authority Layer — single final spatial output for scene geometry."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from backend.core.spatial_canonical_model import canonical_world_to_layout_mm
from backend.core.spatial_contract import SpatialMode


def _score_points(points: Mapping[str, Any]) -> float:
    """Aggregate confidence score for a tag -> point map."""
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


def resolve_spatial_authority(
    *,
    canonical_points: List[Mapping[str, Any]],
    layout_mm_points: Mapping[str, Tuple[float, float]],
    cluster_points: Mapping[str, Tuple[float, float]],
    contract: Mapping[str, Any],
    allowed_tags: Optional[set[str]] = None,
    image_shape: Optional[Tuple[int, int]] = None,
    plan_width_mm: float = 17500.0,
) -> Dict[str, Any]:
    """
    Single decision for final layout-mm coordinates fed to scene equipment.

    ``cluster_points`` is never used for FINAL geometry (debug / proposals only).

    Returns:
      - mode: "FINAL" | "NO_SPATIAL"
      - winner: "canonical" | "layout" | None
      - points: Dict[tag, (x_mm, y_mm)]  (subset or full allowed_tags)
      - reason, scores, proposals_cluster (for debug only)
    """
    c = dict(contract) if isinstance(contract, Mapping) else {}
    mode = str(c.get("spatial_mode") or SpatialMode.DEGRADED).upper()
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

    scores = {
        "canonical": _score_points(canonical_layout),
        "layout": _score_points(layout),
        "cluster": _score_points(cluster),
    }

    if not scene_allowed or mode == SpatialMode.VISUAL_ONLY:
        return {
            "mode": "NO_SPATIAL",
            "winner": None,
            "points": {},
            "reason": "contract disallows scene geometry",
            "scores": scores,
            "proposals_cluster": cluster,
        }

    winner: Optional[str] = None
    if mode == SpatialMode.REAL:
        winner = "canonical" if scores["canonical"] > 0 else "layout"
    elif mode == SpatialMode.DEGRADED:
        if scores["layout"] > 0:
            winner = "layout"
        elif scores["canonical"] > 0:
            winner = "canonical"
        else:
            winner = None
    else:
        winner = "canonical" if scores["canonical"] > 0 else ("layout" if scores["layout"] > 0 else None)

    if winner is None or scores.get(winner, 0) <= 0:
        return {
            "mode": "NO_SPATIAL",
            "winner": None,
            "points": {},
            "reason": "no trusted spatial source",
            "scores": scores,
            "proposals_cluster": cluster,
        }

    src: Dict[str, Tuple[float, float]]
    if winner == "canonical":
        src = dict(canonical_layout)
    else:
        src = dict(layout)

    tags = allowed_tags if allowed_tags is not None else set(src.keys())
    final: Dict[str, Tuple[float, float]] = {}
    for tag in tags:
        if tag in src:
            final[tag] = src[tag]
        else:
            final[tag] = (0.0, 0.0)

    return {
        "mode": "FINAL",
        "winner": winner,
        "points": final,
        "reason": f"authority_winner={winner}",
        "scores": scores,
        "proposals_cluster": cluster,
    }


__all__ = ["resolve_spatial_authority"]
