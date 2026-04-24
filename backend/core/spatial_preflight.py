"""Pre-authority spatial consistency gate (collapse detection, shared anchor context)."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.core.spatial_canonical_model import canonical_world_to_layout_mm


def _trusted_tags(normalized: Sequence[Mapping[str, Any]]) -> set[str]:
    """Exclude cluster_estimate, low confidence, and invalid spatial flags from any geometry stats."""
    out: set[str] = set()
    for row in normalized:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("raw_source", "")) == "cluster_estimate":
            continue
        if not bool(row.get("is_valid_spatial")):
            continue
        if float(row.get("confidence", 0.0) or 0.0) < 0.4:
            continue
        tag = str(row.get("tag") or "").strip()
        if tag:
            out.add(tag)
    return out


def _layout_mm_for_canonical_row(
    row: Mapping[str, Any],
    *,
    image_shape: Tuple[int, int],
    plan_width_mm: float,
) -> Optional[Tuple[float, float]]:
    w, h = int(image_shape[0]), int(image_shape[1])
    if w <= 0:
        return None
    wv = row.get("world")
    if not isinstance(wv, (list, tuple)) or len(wv) < 2:
        return None
    scale = float(plan_width_mm) / float(w)
    return canonical_world_to_layout_mm(
        float(wv[0]),
        float(wv[1]),
        plan_width_mm=plan_width_mm,
        image_height_px=h,
        scale_mm_per_px=scale,
    )


def _centroid(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    n = float(len(points))
    return sx / n, sy / n


def _variance_mmsq(points: List[Tuple[float, float]], cx: float, cy: float) -> float:
    if len(points) < 2:
        return 0.0
    acc = 0.0
    for x, y in points:
        dx = x - cx
        dy = y - cy
        acc += dx * dx + dy * dy
    return acc / float(len(points))


def validate_spatial_consistency(
    canonical_points: Sequence[Mapping[str, Any]],
    layout_points: Mapping[str, Any],
    *,
    normalized_points: Optional[Sequence[Mapping[str, Any]]] = None,
    image_shape: Optional[Tuple[int, int]] = None,
    plan_width_mm: float = 17500.0,
    variance_threshold_mmsq: float = 25.0,
    zero_ratio_threshold: float = 0.40,
) -> Dict[str, Any]:
    """
    Global consistency check before ``resolve_spatial_authority``.

    Cluster / invalid / low-confidence rows never enter centroid, variance, or anchor.
    """
    norm = list(normalized_points or [])
    trusted = _trusted_tags(norm)

    layout_xy: List[Tuple[float, float]] = []
    layout_by_tag: Dict[str, Tuple[float, float]] = {}
    for tag, v in (layout_points or {}).items():
        t = str(tag)
        if t not in trusted:
            continue
        if not isinstance(v, (list, tuple)) or len(v) < 2:
            continue
        xy = (float(v[0]), float(v[1]))
        layout_by_tag[t] = xy
        layout_xy.append(xy)

    issues: List[str] = []
    layout_tags = {str(k) for k in (layout_points or {}).keys()}
    trusted_with_layout = sorted(trusted & layout_tags)
    n_total = max(1, len(trusted_with_layout))
    zero_count = sum(
        1
        for t in trusted_with_layout
        if isinstance(layout_points.get(t), (list, tuple))
        and len(layout_points[t]) >= 2
        and float(layout_points[t][0]) == 0.0
        and float(layout_points[t][1]) == 0.0
    )
    zero_ratio = float(zero_count) / float(n_total)

    gcx, gcy = _centroid(layout_xy)
    global_anchor = [round(gcx, 4), round(gcy, 4)]
    var = _variance_mmsq(layout_xy, gcx, gcy) if layout_xy else 0.0

    collapse_risk = "LOW"
    valid = True

    if len(layout_xy) < 2:
        valid = False
        collapse_risk = "HIGH"
        issues.append("trusted_layout_points_lt_2")
    if zero_ratio > zero_ratio_threshold:
        valid = False
        collapse_risk = "HIGH"
        issues.append(f"zero_layout_ratio_{zero_ratio:.2f}")
    if len(layout_xy) >= 2 and var < variance_threshold_mmsq:
        valid = False
        collapse_risk = "HIGH"
        issues.append(f"low_spatial_variance_{var:.4f}")

    # Per-tag anchor agreement (same transform chain): large drift ⇒ inconsistent inputs.
    max_drift = 0.0
    if image_shape is not None and canonical_points and layout_by_tag:
        for row in canonical_points:
            if not isinstance(row, Mapping):
                continue
            tag = str(row.get("tag") or "").strip()
            if tag not in trusted or tag not in layout_by_tag:
                continue
            mm = _layout_mm_for_canonical_row(row, image_shape=image_shape, plan_width_mm=plan_width_mm)
            if mm is None:
                continue
            lx, ly = layout_by_tag[tag]
            max_drift = max(max_drift, math.hypot(mm[0] - lx, mm[1] - ly))
    if max_drift > 1.0:
        valid = False
        collapse_risk = "HIGH"
        issues.append(f"canonical_layout_anchor_drift_mm_{max_drift:.4f}")
    elif canonical_points and layout_xy and max_drift > 0.001:
        if collapse_risk == "LOW":
            collapse_risk = "MEDIUM"
        issues.append(f"canonical_layout_minor_drift_mm_{max_drift:.6f}")

    return {
        "valid": bool(valid),
        "issues": issues,
        "global_anchor": global_anchor,
        "variance": round(float(var), 6),
        "collapse_risk": collapse_risk,
        "trusted_point_count": len(layout_xy),
        "zero_ratio": round(zero_ratio, 4),
        "max_anchor_drift_mm": round(float(max_drift), 6),
    }


__all__ = ["validate_spatial_consistency"]
