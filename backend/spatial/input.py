"""Raw spatial input loading helpers."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple


def load_points(raw_pixel_data: Mapping[str, Any]) -> Dict[str, Tuple[float, float]]:
    """
    Input: raw pixel data (OCR / pickpoint / manual)
    Output: cleaned pixel points {tag: (x_px, y_px)}
    """
    out: Dict[str, Tuple[float, float]] = {}
    for tag, value in dict(raw_pixel_data or {}).items():
        x = None
        y = None
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            x, y = value[0], value[1]
        elif isinstance(value, Mapping):
            if "pos" in value and isinstance(value.get("pos"), (list, tuple)):
                pos = value.get("pos")
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    x, y = pos[0], pos[1]
            else:
                x = value.get("x")
                y = value.get("y")
        if x is None or y is None:
            continue
        try:
            out[str(tag)] = (float(x), float(y))
        except (TypeError, ValueError):
            continue
    return out


__all__ = ["load_points"]
