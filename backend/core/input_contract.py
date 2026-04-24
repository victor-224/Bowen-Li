"""Input consistency contract: classify completeness without blocking execution.

This module is intentionally lightweight and non-intrusive. It does not alter
pipeline behavior; it only annotates input quality for observability/UI.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.asset_contract import safe_load_image


class InputState:
    VALID = "valid"
    DEGRADED_LAYOUT = "degraded_layout"
    MISSING_LAYOUT = "missing_layout"
    PARTIAL = "partial"


def evaluate_input_contract(excel: Any, layout_image: Any, plan_path: str | None = None) -> Dict[str, Any]:
    """
    Evaluate input completeness for scene/pipeline observability.

    Parameters are permissive by design:
      - ``excel``: truthy when equipment source is available
      - ``layout_image``: path-like or object (if preloaded image object)
      - ``plan_path``: optional explicit path string
    """
    warnings: List[str] = []

    excel_available = bool(excel)
    path = plan_path if plan_path is not None else (str(layout_image) if layout_image is not None else None)
    layout_present = bool(path)

    layout_available = False
    if layout_present and isinstance(path, str):
        layout_available = safe_load_image(path) is not None
    elif layout_image is not None and not isinstance(layout_image, (str, bytes)):
        # pre-loaded object path: assume available if caller already decoded it
        layout_available = True

    if excel_available and layout_available:
        state = InputState.VALID
    elif excel_available and not layout_present:
        state = InputState.DEGRADED_LAYOUT
        warnings.append("layout_missing")
    elif excel_available and layout_present and not layout_available:
        state = InputState.MISSING_LAYOUT
        warnings.append("layout_unreadable")
    else:
        state = InputState.PARTIAL
        if not excel_available:
            warnings.append("excel_missing")
        if not layout_available:
            warnings.append("layout_missing_or_unreadable")

    return {
        "state": state,
        "layout_available": bool(layout_available),
        "excel_available": bool(excel_available),
        "warnings": warnings,
    }


__all__ = ["InputState", "evaluate_input_contract"]
