"""Single spatial transform: pixel -> world."""

from __future__ import annotations

from typing import Dict, Mapping, Tuple


class SpatialFrame:
    """Convert image pixel coordinates into world coordinates in millimetres."""

    def __init__(self, img_width: int, img_height: int, scale_mm_per_px: float):
        self.cx = img_width / 2.0
        self.cy = img_height / 2.0
        self.scale = float(scale_mm_per_px)

    def pixel_to_world(self, x_px: float, y_px: float) -> Tuple[float, float]:
        x_world = (float(x_px) - self.cx) * self.scale
        y_world = (self.cy - float(y_px)) * self.scale
        return x_world, y_world


def pixel_to_world(
    points: Mapping[str, Tuple[float, float]],
    img_shape: Tuple[int, int],
    plan_width_mm: float = 17500.0,
) -> Dict[str, Tuple[float, float]]:
    """
    Single coordinate system: image center as origin.

    img_shape = (width, height)
    """
    w, h = int(img_shape[0]), int(img_shape[1])
    if w <= 0:
        raise ValueError(f"Invalid image width: {w}")
    scale = float(plan_width_mm) / float(w)
    frame = SpatialFrame(img_width=w, img_height=h, scale_mm_per_px=scale)
    return {
        str(tag): frame.pixel_to_world(float(x), float(y))
        for tag, (x, y) in dict(points or {}).items()
    }


__all__ = ["SpatialFrame", "pixel_to_world"]
