"""Layer 2: build canonical spatial model (image-center anchor, mm world)."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from backend.core.spatial_frame import SpatialFrame


def canonical_world_to_layout_mm(
    world_x: float,
    world_y: float,
    *,
    plan_width_mm: float,
    image_height_px: int,
    scale_mm_per_px: float,
) -> Tuple[float, float]:
    """Map canonical world (center origin) back to legacy layout-mm for scene engine."""
    height_mm = float(scale_mm_per_px) * float(image_height_px)
    return world_x + float(plan_width_mm) / 2.0, world_y + height_mm / 2.0


def build_canonical_space(
    normalized_points: List[Mapping[str, Any]],
    image_shape: Tuple[int, int],
    *,
    plan_width_mm: float = 17500.0,
) -> List[Dict[str, Any]]:
    """
    Only points with ``is_valid_spatial`` True enter the canonical model.

    ``image_shape`` is (width_px, height_px). Anchor = image center.
    """
    w, h = int(image_shape[0]), int(image_shape[1])
    if w <= 0:
        raise ValueError(f"Invalid image width: {w}")
    scale = float(plan_width_mm) / float(w)
    frame = SpatialFrame(w, h, scale)
    out: List[Dict[str, Any]] = []
    for row in normalized_points:
        if not isinstance(row, Mapping):
            continue
        if not bool(row.get("is_valid_spatial")):
            continue
        tag = str(row.get("tag") or "").strip()
        if not tag:
            continue
        pix = row.get("pixel")
        if not isinstance(pix, (list, tuple)) or len(pix) < 2:
            continue
        x_px, y_px = float(pix[0]), float(pix[1])
        wx, wy = frame.pixel_to_world(x_px, y_px)
        out.append(
            {
                "tag": tag,
                "world": (wx, wy),
                "confidence": float(row.get("confidence", 0.0) or 0.0),
                "source": str(row.get("source") or "fallback"),
                "anchor": "image_center",
                "frame": "canonical_v1",
            }
        )
    return out


__all__ = ["build_canonical_space", "canonical_world_to_layout_mm"]
