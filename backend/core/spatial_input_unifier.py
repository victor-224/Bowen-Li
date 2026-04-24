"""Unified spatial input layer (single orchestration entry before scene geometry).

This module collapses multi-step spatial candidate handling into one place:
detected -> normalized -> canonical -> preflight -> authority.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import cv2

from backend.core.spatial_authority import resolve_spatial_authority
from backend.core.spatial_canonical_model import build_canonical_space
from backend.core.spatial_contract import SpatialMode
from backend.core.spatial_preflight import validate_spatial_consistency
from backend.core.spatial_source_normalizer import normalize_spatial_sources
from backend.locator import pixel_to_mm
from backend.opencv_util import opencv_imread_quiet


def unify_spatial_input(
    *,
    detected: Mapping[str, Any],
    allowed_tags: set[str],
    safe_plan: Path,
    spatial_contract: Mapping[str, Any],
    plan_width_mm: float = 17500.0,
) -> Dict[str, Any]:
    """Return a single spatial decision payload for scene consumption."""
    pixel_positions: Dict[str, tuple[int, int]] = {}
    raw_points: list[dict[str, object]] = []
    for tag, v in detected.items():
        if isinstance(v, dict):
            p = v.get("pos", [0, 0])
            pixel_positions[str(tag)] = (int(p[0]), int(p[1]))
            raw_points.append(
                {
                    "tag": str(tag),
                    "pos": [int(p[0]), int(p[1])],
                    "confidence": float(v.get("confidence", 0.0)),
                    "source": str(v.get("source") or "unknown"),
                }
            )
        else:
            pixel_positions[str(tag)] = (int(v[0]), int(v[1]))
            raw_points.append(
                {
                    "tag": str(tag),
                    "pos": [int(v[0]), int(v[1])],
                    "confidence": 0.7,
                    "source": "unknown",
                }
            )

    normalized = normalize_spatial_sources(raw_points)

    with opencv_imread_quiet():
        img = cv2.imread(str(safe_plan), cv2.IMREAD_COLOR)
    image_shape: tuple[int, int] | None = None
    canonical: list[dict[str, Any]] = []
    if img is not None:
        h, w = img.shape[:2]
        image_shape = (w, h)
        canonical = build_canonical_space(normalized, image_shape, plan_width_mm=plan_width_mm)

    layout_points = pixel_to_mm(pixel_positions, safe_plan, plan_width_mm=plan_width_mm)
    cluster_points: Dict[str, tuple[float, float]] = {}
    for tag, v in detected.items():
        if isinstance(v, dict) and str(v.get("source")) == "cluster_estimate":
            t = str(tag)
            if t in layout_points:
                cluster_points[t] = layout_points[t]

    preflight = validate_spatial_consistency(
        canonical_points=canonical,
        layout_points=layout_points,
        normalized_points=normalized,
        image_shape=image_shape,
        plan_width_mm=plan_width_mm,
    )

    contract_for_authority = dict(spatial_contract)
    if not bool(preflight.get("valid")):
        contract_for_authority = {
            **contract_for_authority,
            "spatial_valid": False,
            "scene_allowed": False,
            "spatial_mode": SpatialMode.DEGRADED,
            "reason": "preflight spatial collapse detected",
        }

    authority = resolve_spatial_authority(
        canonical_points=canonical,
        layout_mm_points=layout_points,
        cluster_points=cluster_points,
        contract=contract_for_authority,
        allowed_tags=allowed_tags,
        image_shape=image_shape,
        plan_width_mm=plan_width_mm,
        normalized_points=normalized,
    )

    positions: Dict[str, tuple[float, float]] = {}
    for tag, xy in (authority.get("points") or {}).items():
        if isinstance(xy, (list, tuple)) and len(xy) >= 2:
            positions[str(tag)] = (float(xy[0]), float(xy[1]))

    confidence_map = {
        str(k): float(v)
        for k, v in (authority.get("confidence_map") or {}).items()
    }

    return {
        "positions": positions,
        "confidence_map": confidence_map,
        "normalized": normalized,
        "canonical": canonical,
        "preflight": preflight,
        "authority": authority,
        "spatial_contract_for_authority": contract_for_authority,
    }


__all__ = ["unify_spatial_input"]
