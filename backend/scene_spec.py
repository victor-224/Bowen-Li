"""
Unified scene document shape (contract only).

This module defines how scene JSON is assembled: field names, nesting, meta defaults,
and helpers to build each equipment entry. It does not implement placement algorithms,
3D mesh generation, or rendering.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

# Plan scale reference (mm across image width) — informational for consumers
SCENE_SCALE_MM = 17500
SCENE_SOURCE = "Annexe 1 + 2"

# Canonical keys on each equipment item (see module docstring)
EQUIPMENT_KEYS = ("tag", "service", "geometry_type", "position_mm", "dimensions")


def default_meta(overrides: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Default scene.meta; optional shallow overrides."""
    meta: Dict[str, Any] = {"scale": SCENE_SCALE_MM, "source": SCENE_SOURCE}
    if overrides:
        meta.update(dict(overrides))
    return meta


def dimensions_from_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Nest diameter / length / height from a flat Excel-style row into dimensions."""
    return {
        "diameter": row.get("diameter"),
        "length": row.get("length"),
        "height": row.get("height"),
    }


def infer_geometry_type(service: Any) -> str:
    """
    Label-only geometry class from service name (no mesh construction).
    Same classification rules as geometry_engine Phase-4 baseline.
    """
    s = str(service) if service is not None else ""
    if "Tank" in s:
        return "cylinder_vertical"
    if "Exchanger" in s:
        return "cylinder_horizontal"
    if "Compressor" in s:
        return "box"
    return "cylinder"


def equipment_item(
    tag: str,
    service: Any,
    position_mm_xy: Sequence[float],
    dimensions: Mapping[str, Any],
    geometry_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    One equipment record in canonical scene form.

    position_mm: [x, y] in millimetres (plan / 2D placement).
    """
    x = float(position_mm_xy[0]) if len(position_mm_xy) > 0 else 0.0
    y = float(position_mm_xy[1]) if len(position_mm_xy) > 1 else 0.0
    gt = geometry_type if geometry_type is not None else infer_geometry_type(service)
    return {
        "tag": tag,
        "service": "" if service is None else str(service),
        "geometry_type": gt,
        "position_mm": [x, y],
        "dimensions": {
            "diameter": dimensions.get("diameter"),
            "length": dimensions.get("length"),
            "height": dimensions.get("height"),
        },
    }


def build_equipment_list(
    rows: Sequence[Mapping[str, Any]],
    positions_mm: Mapping[str, Union[Sequence[float], Tuple[float, float]]],
) -> List[Dict[str, Any]]:
    """
    Build equipment[] from list rows (each must include 'tag' and Excel fields).

    positions_mm: tag -> [x_mm, y_mm] or (x_mm, y_mm); missing tags default to [0, 0].
    """
    out: List[Dict[str, Any]] = []
    for row in rows:
        tag = str(row.get("tag", ""))
        if not tag:
            continue
        pos = positions_mm.get(tag, (0.0, 0.0))
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            xy = [float(pos[0]), float(pos[1])]
        else:
            xy = [0.0, 0.0]
        dims = dimensions_from_row(row)
        out.append(
            equipment_item(
                tag=tag,
                service=row.get("service"),
                position_mm_xy=xy,
                dimensions=dims,
            )
        )
    return out


def empty_scene(meta_overrides: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Minimal valid scene shell."""
    return {
        "equipment": [],
        "walls": [],
        "meta": default_meta(meta_overrides),
    }
