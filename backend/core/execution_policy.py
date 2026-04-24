"""Deterministic execution policy from input contract state.

This module does not execute tools or alter pipeline structure.
It only maps input quality -> policy hints for existing layers.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.core.input_contract import InputState


def _base() -> Dict[str, Any]:
    return {
        "mode": "preview",
        "tool_filters": [],
        "scene_mode": "equipment_only",
        "ai_usage_level": "disabled",
        "notes": [],
    }


def resolve_execution_policy(contract: dict) -> dict:
    """Map input contract state to policy hints.

    Output format:
    {
      "mode": "full | degraded | minimal | preview",
      "tool_filters": [],
      "scene_mode": "full_scene | simplified_scene | equipment_only",
      "ai_usage_level": "full | reduced | disabled",
      "notes": []
    }
    """
    c = contract if isinstance(contract, dict) else {}
    state = str(c.get("state") or InputState.PARTIAL)
    out = _base()
    notes: List[str] = []

    if state == InputState.VALID:
        out.update(
            {
                "mode": "full",
                "scene_mode": "full_scene",
                "ai_usage_level": "full",
            }
        )
    elif state == InputState.DEGRADED_LAYOUT:
        out.update(
            {
                "mode": "degraded",
                "scene_mode": "simplified_scene",
                "ai_usage_level": "reduced",
            }
        )
        notes.append("layout missing or invalid")
    elif state == InputState.MISSING_LAYOUT:
        out.update(
            {
                "mode": "minimal",
                "scene_mode": "equipment_only",
                "ai_usage_level": "reduced",
            }
        )
        notes.append("no spatial data available")
    else:
        # PARTIAL (or unknown): safest preview profile
        out.update(
            {
                "mode": "preview",
                "scene_mode": "equipment_only",
                "ai_usage_level": "disabled",
            }
        )
        notes.append("incomplete input")

    extra = c.get("warnings")
    if isinstance(extra, list):
        for w in extra:
            if isinstance(w, str) and w not in notes:
                notes.append(w)
    out["notes"] = notes
    return out


__all__ = ["resolve_execution_policy"]
