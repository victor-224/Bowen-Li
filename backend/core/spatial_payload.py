"""Global spatial payload sanitizer.

Ensures no fake/synthetic spatial geometry leaks when spatial scene is disallowed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

def _sanitize_scene_items(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for row in items:
        if not isinstance(row, dict):
            continue
        cleaned = dict(row)
        # Remove all coordinate-bearing fields from scene payload in no-spatial mode.
        cleaned.pop("position_mm", None)
        cleaned.pop("x", None)
        cleaned.pop("y", None)
        cleaned.pop("z", None)
        out.append(cleaned)
    return out


def sanitize_spatial_payload(
    payload: Mapping[str, Any],
    *,
    route: str | None = None,
) -> Dict[str, Any]:
    """Return a sanitized payload based on spatial contract global rule.

    Rule:
    if spatial_contract.scene_allowed == False:
      - strip coordinate-bearing scene fields
      - clear potentially synthetic relations/walls
      - preserve equipment metadata + contracts + policy
    """
    p = dict(payload or {})
    contract = p.get("spatial_contract")
    if not isinstance(contract, dict):
        return p
    if bool(contract.get("scene_allowed")):
        return p

    p["scene"] = _sanitize_scene_items(p.get("scene"))
    p["walls"] = {"walls": [], "rooms": [], "center": [0.0, 0.0]}
    p["relations"] = {}
    p["spatial_warning"] = "Equipment Only Mode: no spatial scene available."
    # File may still decode; spatial pipeline is not using it for geometry.
    insp = dict(p.get("layout_inspector") or {})
    insp["used_for_spatial"] = False
    p["layout_inspector"] = insp
    if route:
        p["spatial_sanitized_route"] = str(route)
    return p


__all__ = ["sanitize_spatial_payload"]
