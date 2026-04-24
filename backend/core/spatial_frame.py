"""Centered spatial frame: deterministic pixel → plan layout (mm) transform.

Image pixels use top-left origin (x right, y down). Plan layout mm use the
legacy convention from ``pixel_to_mm``: x grows with pixel x; y grows toward
the physical "up" direction of the drawing (image y inverted).

The ``SpatialFrame`` class expresses the intermediate step in **centered
world** coordinates (origin at image center, y up). Public helper
``pixel_to_layout_mm`` composes frame + offset so callers keep the same
numeric contract as the previous ad-hoc formulas.
"""

from __future__ import annotations


class SpatialFrame:
    """
    Convert image pixel coordinates into centered world coordinates (mm),
    then compose to plan layout mm via ``pixel_to_layout_mm``.
    """

    def __init__(self, img_width: int, img_height: int, scale_mm_per_px: float) -> None:
        self.cx = float(img_width) / 2.0
        self.cy = float(img_height) / 2.0
        self.scale = float(scale_mm_per_px)

    def pixel_to_world(self, x_px: float, y_px: float) -> tuple[float, float]:
        """
        Centered world (mm): origin at image center, x → right, y → up
        (inverted from image row coordinates).
        """
        x_world = (float(x_px) - self.cx) * self.scale
        y_world = (self.cy - float(y_px)) * self.scale
        return x_world, y_world


def pixel_to_layout_mm(
    x_px: float,
    y_px: float,
    img_width: int,
    img_height: int,
    plan_width_mm: float,
) -> tuple[float, float]:
    """
    Same layout-mm values as legacy ``x * scale`` and ``(img_height - y) * scale``.

    ``plan_width_mm`` is the physical width represented by the full image width.
    """
    w = int(img_width)
    h = int(img_height)
    if w <= 0:
        raise ValueError(f"Invalid plan width: {w}")
    scale = float(plan_width_mm) / float(w)
    frame = SpatialFrame(w, h, scale)
    x_w, y_w = frame.pixel_to_world(x_px, y_px)
    height_mm = scale * float(h)
    x_mm = x_w + float(plan_width_mm) / 2.0
    y_mm = y_w + height_mm / 2.0
    return x_mm, y_mm


__all__ = ["SpatialFrame", "pixel_to_layout_mm"]
