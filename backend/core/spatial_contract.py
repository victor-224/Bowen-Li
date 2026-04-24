"""Spatial integrity contract for coordinate trust and scene gating.

This layer classifies whether extracted spatial coordinates are trusted for
scene geometry usage. It does not run extraction itself.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping


class SpatialMode:
    REAL = "REAL"
    DEGRADED = "DEGRADED"
    VISUAL_ONLY = "VISUAL_ONLY"


def make_spatial_contract(
    *,
    spatial_valid: bool,
    spatial_mode: str,
    source: str,
    scene_allowed: bool,
    visual_allowed: bool = True,
    reason: str = "",
) -> Dict[str, Any]:
    return {
        "spatial_valid": bool(spatial_valid),
        "spatial_mode": str(spatial_mode),
        "source": str(source or "unknown"),
        "scene_allowed": bool(scene_allowed),
        "visual_allowed": bool(visual_allowed),
        "reason": str(reason or ""),
    }


def resolve_spatial_contract(
    *,
    plan_loaded: bool,
    detected_positions: Mapping[str, Any] | None = None,
    detected: Mapping[str, Any] | None = None,
    pickpoint_active: bool = False,
) -> Dict[str, Any]:
    """
    Build authoritative spatial contract from extraction context.

    Output shape:
    {
      "spatial_valid": bool,
      "spatial_mode": "REAL | DEGRADED | VISUAL_ONLY",
      "source": "plan | pickpoint | cache | cluster_estimate | unknown",
      "scene_allowed": bool,
      "visual_allowed": True,
      "reason": str
    }
    """
    detected_map = detected_positions or detected or {}
    sources: set[str] = set()
    if isinstance(detected_map, Mapping):
        for v in detected_map.values():
            if isinstance(v, Mapping):
                s = str(v.get("source") or "").strip()
                if s:
                    sources.add(s)
                if bool(v.get("visual_only", False)):
                    sources.add("cluster_estimate")

    has_pickpoint = pickpoint_active or ("pickpoint" in sources)
    has_cluster = "cluster_estimate" in sources
    has_plan_extract = bool({"ocr", "pdf_text", "ocr_vote"} & sources)
    has_cache = "cache" in sources

    # Rule 1: REAL = trusted extraction from readable plan or pickpoint.
    if (plan_loaded and has_plan_extract) or has_pickpoint:
        return make_spatial_contract(
            spatial_valid=True,
            spatial_mode=SpatialMode.REAL,
            source="pickpoint" if has_pickpoint else "plan",
            scene_allowed=True,
            visual_allowed=True,
            reason="trusted spatial source available",
        )

    # Rule 3: VISUAL_ONLY = synthetic cluster fallback is active.
    if has_cluster:
        return make_spatial_contract(
            spatial_valid=False,
            spatial_mode=SpatialMode.VISUAL_ONLY,
            source="cluster_estimate",
            scene_allowed=False,
            visual_allowed=True,
            reason="synthetic fallback active; blocked from scene geometry",
        )

    # Rule 2: DEGRADED = no trusted geometry source.
    if not plan_loaded:
        return make_spatial_contract(
            spatial_valid=False,
            spatial_mode=SpatialMode.DEGRADED,
            source="cache" if has_cache else "unknown",
            scene_allowed=False,
            visual_allowed=True,
            reason="plan missing or unreadable and no trusted spatial source",
        )

    # Readable plan but no usable detections.
    return make_spatial_contract(
        spatial_valid=False,
        spatial_mode=SpatialMode.DEGRADED,
        source="cache" if has_cache else "unknown",
        scene_allowed=False,
        visual_allowed=True,
        reason="no trusted spatial detections",
    )


build_spatial_integrity_contract = make_spatial_contract

__all__ = [
    "SpatialMode",
    "make_spatial_contract",
    "build_spatial_integrity_contract",
    "resolve_spatial_contract",
]

