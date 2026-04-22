"""Phase 2: basic automatic layout (2D positions in mm)."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple


def layout_engine(equipements: Mapping[str, Mapping[str, Any]]) -> Dict[str, Tuple[float, float]]:
    """
    Basic automatic layout:
    - group by service name
    - linear arrangement within each group
    - produce initial 2D coordinates (mm)

    Returns:
        tag -> (x_mm, y_mm)
    """
    zones: Dict[str, list[str]] = {}
    result: Dict[str, Tuple[float, float]] = {}

    spacing = 3000.0

    for tag, e in equipements.items():
        zone_key = e.get("service")
        if zone_key is None or (isinstance(zone_key, str) and not zone_key.strip()):
            zone_key = "Unknown"
        else:
            zone_key = str(zone_key)
        zones.setdefault(zone_key, []).append(tag)

    zone_order = sorted(zones.keys())
    for zone in zone_order:
        tags = sorted(zones[zone])
        x_base = 0.0
        y_base = float(zone_order.index(zone) * 8000)

        for i, tag in enumerate(tags):
            result[tag] = (x_base + i * spacing, y_base)

    return result
