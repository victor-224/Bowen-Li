"""Centralized deterministic policy engine.

This module computes behavior hints from existing truth contracts and runtime
context. It does not execute tools, mutate pipeline state, or alter contracts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from backend.core.spatial_contract import SpatialMode


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _base_policy() -> Dict[str, Any]:
    return {
        "execution_mode": "MINIMAL",
        "scene_mode": "EMPTY",
        "ai_mode": "OFF",
        "tool_policy": {
            "allow_vision": False,
            "allow_fallback": True,
            "allow_cluster_estimate": False,
        },
        "spatial_policy": {
            "allow_spatial_scene": False,
            "allow_visual_only": True,
        },
        "reasoning": [],
    }


def resolve_policy(
    contract: Dict[str, Any],
    ai_status: Optional[Dict[str, Any]] = None,
    runtime_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute unified execution policy from contract + context."""
    c: Mapping[str, Any] = contract if isinstance(contract, dict) else {}
    ai: Mapping[str, Any] = ai_status if isinstance(ai_status, dict) else {}
    ctx: Mapping[str, Any] = runtime_context if isinstance(runtime_context, dict) else {}

    mode = str(c.get("spatial_mode") or SpatialMode.DEGRADED).upper()
    spatial_valid = _bool(c.get("spatial_valid"))
    scene_allowed = _bool(c.get("scene_allowed"))
    source = str(c.get("source") or "unknown")

    ai_reachable = _bool(ai.get("reachable"), default=True)
    ai_enabled = _bool(ctx.get("enable_ai"), default=True)
    low_resource = _bool(ctx.get("low_resource_mode"), default=False)

    out = _base_policy()
    reasoning: List[str] = []

    if mode == SpatialMode.REAL and spatial_valid and scene_allowed:
        out.update(
            {
                "execution_mode": "FULL",
                "scene_mode": "FULL_SCENE",
                "ai_mode": "FULL",
            }
        )
        out["tool_policy"]["allow_vision"] = True
        out["spatial_policy"]["allow_spatial_scene"] = True
        reasoning.append("trusted spatial contract allows full scene execution")
    elif mode == SpatialMode.VISUAL_ONLY:
        out.update(
            {
                "execution_mode": "VISUAL_ONLY",
                "scene_mode": "EMPTY",
                "ai_mode": "REDUCED",
            }
        )
        out["tool_policy"]["allow_vision"] = False
        out["tool_policy"]["allow_cluster_estimate"] = False
        out["spatial_policy"]["allow_spatial_scene"] = False
        reasoning.append("visual-only spatial contract blocks geometry usage")
    else:
        out.update(
            {
                "execution_mode": "DEGRADED",
                "scene_mode": "SIMPLIFIED",
                "ai_mode": "REDUCED",
            }
        )
        out["tool_policy"]["allow_vision"] = False
        out["spatial_policy"]["allow_spatial_scene"] = False
        reasoning.append("degraded spatial contract limits scene + ai")

    if not ai_enabled or not ai_reachable:
        out["ai_mode"] = "OFF"
        out["tool_policy"]["allow_vision"] = False
        reasoning.append("ai unavailable or disabled by runtime context")
    elif low_resource and out["ai_mode"] == "FULL":
        out["ai_mode"] = "REDUCED"
        reasoning.append("low_resource_mode reduces ai usage")

    if source == "cluster_estimate":
        out["tool_policy"]["allow_cluster_estimate"] = False
        reasoning.append("cluster estimate is restricted to visual context only")

    out["reasoning"] = reasoning
    return out


__all__ = ["resolve_policy"]

