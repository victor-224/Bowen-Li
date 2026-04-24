"""Plan wall/room parsing using OpenCV (threshold, contour, hough line)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from backend.opencv_util import opencv_imread_quiet
from backend.core.spatial_frame import pixel_to_layout_mm


def _pixel_to_mm(x: float, y: float, w: int, h: int, plan_width_mm: float) -> List[float]:
    """Convert image pixel to plan layout mm (same contract as ``locator.pixel_to_mm``)."""
    x_mm, y_mm = pixel_to_layout_mm(x, y, w, h, plan_width_mm)
    return [round(float(x_mm), 3), round(float(y_mm), 3)]


def parse_walls_and_rooms(
    plan_path: Path,
    plan_width_mm: float = 17500.0,
) -> Dict[str, Any]:
    """
    Extract simplified wall/room structure from plan image.

    Uses:
    - threshold (binary inversion)
    - contour (outer boundary + room-like regions)
    - hough line (wall line candidates)
    """
    with opencv_imread_quiet():
        img = cv2.imread(str(plan_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot read plan image: {plan_path}")
    h, w = img.shape[:2]
    if w <= 0:
        raise ValueError(f"Invalid plan image width: {w}")
    scale = float(plan_width_mm) / float(w)

    # 1) threshold
    _, th = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 2) contour
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    outer_contour = max(contours, key=cv2.contourArea) if contours else None

    # 3) hough line
    lines = cv2.HoughLinesP(
        th,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=max(20, int(w * 0.03)),
        maxLineGap=max(5, int(w * 0.01)),
    )

    walls: List[Dict[str, Any]] = []
    if lines is not None:
        for l in lines[:800]:
            x1, y1, x2, y2 = l[0]
            p1 = _pixel_to_mm(x1, y1, w, h, plan_width_mm)
            p2 = _pixel_to_mm(x2, y2, w, h, plan_width_mm)
            walls.append(
                {
                    "type": "wall_line",
                    "p1_mm": p1,
                    "p2_mm": p2,
                }
            )

    if outer_contour is not None:
        peri = cv2.arcLength(outer_contour, True)
        approx = cv2.approxPolyDP(outer_contour, 0.005 * peri, True)
        poly = [_pixel_to_mm(pt[0][0], pt[0][1], w, h, plan_width_mm) for pt in approx]
        walls.append({"type": "outer_boundary", "polygon_mm": poly})

    rooms: List[Dict[str, Any]] = []
    for c in contours:
        area = cv2.contourArea(c)
        # Ignore too small contours and the full-page outer boundary.
        if area < (w * h * 0.002) or area > (w * h * 0.95):
            continue
        x, y, rw, rh = cv2.boundingRect(c)
        center_px = (x + rw / 2.0, y + rh / 2.0)
        x_mm_tl, _ = pixel_to_layout_mm(x, y, w, h, plan_width_mm)
        _, y_mm_bl = pixel_to_layout_mm(x, y + rh, w, h, plan_width_mm)
        rooms.append(
            {
                "bbox_mm": {
                    "x": round(x_mm_tl, 3),
                    "y": round(y_mm_bl, 3),
                    "width": round(rw * scale, 3),
                    "height": round(rh * scale, 3),
                },
                "center_mm": _pixel_to_mm(center_px[0], center_px[1], w, h, plan_width_mm),
            }
        )

    cx_mm, cy_mm = pixel_to_layout_mm(w / 2.0, h / 2.0, w, h, plan_width_mm)
    center = [round(cx_mm, 3), round(cy_mm, 3)]
    return {"walls": walls, "rooms": rooms, "center": center}

