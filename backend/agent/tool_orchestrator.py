"""Unified tool orchestration: intent → internal plan → validate → execute (whitelist only).

Merges planner + executor into one controlled layer. Does not invoke the full
async pipeline DAG, ``exec``, or dynamic code. Tools are explicit callables only.

Optional use: inject ``runtime_state`` for ``get_task_status`` and cache clear
after ``repair_assets`` / ``rebuild_scene``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.agent.execution_trace import ExecutionTrace

logger = logging.getLogger("industrial_digital_twin.tool_orchestrator")

MAX_STEPS = 5

ALLOWED_TOOLS = frozenset(
    {
        "retry_ocr",
        "rebuild_scene",
        "repair_assets",
        "get_task_status",
        "validate_layout",
    }
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runtime_plan() -> Path:
    return _repo_root() / "data" / "runtime" / "plan.png"


def _runtime_excel() -> Path:
    return _repo_root() / "data" / "runtime" / "equipment.xlsx"


def _tool_retry_ocr(args: Dict[str, Any], runtime_state: Any) -> Dict[str, Any]:
    """Re-run OCR/position detection only (no full graph build)."""
    from backend.locator import detect_positions_with_confidence

    plan = _runtime_plan()
    if not plan.is_file():
        return {"ok": False, "error": "plan.png missing", "positions": {}}
    positions = detect_positions_with_confidence(plan)
    return {"ok": True, "position_count": len(positions), "positions": positions}


def _tool_rebuild_scene(args: Dict[str, Any], runtime_state: Any) -> Dict[str, Any]:
    """Build scene document from current Excel + plan (does not submit async task)."""
    from backend.api import load_equipment_from_excel
    from backend.engines.scene import build_scene_document

    if not _runtime_excel().is_file():
        return {"ok": False, "error": "equipment.xlsx missing"}
    equipment = load_equipment_from_excel(_runtime_excel())
    doc = build_scene_document(equipment, plan_path=_runtime_plan())
    if runtime_state is not None and hasattr(runtime_state, "clear_pipeline_cache"):
        n = runtime_state.clear_pipeline_cache()
        return {"ok": True, "scene_equipment_count": len(doc.get("equipment", [])), "cache_cleared": n}
    return {"ok": True, "scene_equipment_count": len(doc.get("equipment", []))}


def _tool_repair_assets(args: Dict[str, Any], runtime_state: Any) -> Dict[str, Any]:
    """Validate plan image contract; clear pipeline cache so next read rebuilds."""
    from backend.asset_contract import PLAN_IMAGE_CONTRACT, validate_asset

    try:
        validate_asset(PLAN_IMAGE_CONTRACT, stage="tool_orchestrator")
        msg = "plan.png valid"
    except Exception as e:  # noqa: BLE001
        msg = str(e)
    cleared = 0
    if runtime_state is not None and hasattr(runtime_state, "clear_pipeline_cache"):
        cleared = runtime_state.clear_pipeline_cache()
    return {"ok": True, "validation_message": msg, "cache_cleared": cleared}


def _tool_get_task_status(args: Dict[str, Any], runtime_state: Any) -> Dict[str, Any]:
    if runtime_state is None:
        return {"ok": False, "error": "runtime_state not configured"}
    tid = (args.get("task_id") or "").strip()
    if not tid:
        return {"ok": False, "error": "task_id required"}
    rec = runtime_state.get_task(tid)
    if rec is None:
        return {"ok": False, "error": "task not found", "task_id": tid}
    return {"ok": True, "task": dict(rec)}


def _tool_validate_layout(args: Dict[str, Any], runtime_state: Any) -> Dict[str, Any]:
    """Light checks: Excel sheet + plan readability (no OCR run)."""
    from backend.api import SHEET_NAME, load_equipment_from_excel
    import cv2

    issues: List[str] = []
    if not _runtime_excel().is_file():
        issues.append("equipment.xlsx missing")
    else:
        try:
            load_equipment_from_excel(_runtime_excel())
        except Exception as e:  # noqa: BLE001
            issues.append(f"excel: {e}")
    if not _runtime_plan().is_file():
        issues.append("plan.png missing")
    else:
        img = cv2.imread(str(_runtime_plan()), cv2.IMREAD_COLOR)
        if img is None:
            issues.append("plan.png unreadable")
    return {"ok": len(issues) == 0, "issues": issues}


_TOOL_REGISTRY: Dict[str, Callable[[Dict[str, Any], Any], Dict[str, Any]]] = {
    "retry_ocr": _tool_retry_ocr,
    "rebuild_scene": _tool_rebuild_scene,
    "repair_assets": _tool_repair_assets,
    "get_task_status": _tool_get_task_status,
    "validate_layout": _tool_validate_layout,
}


def _normalize_args(args: Any) -> Dict[str, Any]:
    if args is None:
        return {}
    if isinstance(args, dict):
        return dict(args)
    return {}


def _validate_step(step: Any) -> Tuple[bool, str]:
    if not isinstance(step, dict):
        return False, "step must be object"
    tool = step.get("tool")
    if not isinstance(tool, str) or tool not in ALLOWED_TOOLS:
        return False, f"tool not allowed: {tool!r}"
    if not isinstance(step.get("args", {}), dict):
        return False, "args must be object"
    return True, ""


def _plan_from_context(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Internal plan generation only (not exposed as separate module)."""
    intent = str(context.get("intent") or context.get("type") or "user_request").lower()
    explicit = context.get("steps")
    if isinstance(explicit, list) and explicit:
        return [s for s in explicit if isinstance(s, dict)][:MAX_STEPS]

    if intent in ("error_recovery", "recovery", "repair"):
        return [
            {"tool": "validate_layout", "args": {}, "reason": "check inputs"},
            {"tool": "repair_assets", "args": {}, "reason": "validate plan asset + clear cache"},
            {"tool": "retry_ocr", "args": {}, "reason": "refresh positions"},
            {"tool": "rebuild_scene", "args": {}, "reason": "rebuild scene snapshot"},
        ]
    if intent in ("vision_task", "vision"):
        return [
            {"tool": "validate_layout", "args": {}, "reason": "ensure plan readable"},
        ]
    tid = context.get("task_id")
    if tid:
        return [{"tool": "get_task_status", "args": {"task_id": str(tid)}, "reason": "user asked for task status"}]
    return [
        {"tool": "validate_layout", "args": {}, "reason": "default health check"},
    ]


def execute_intent(
    context: Dict[str, Any],
    *,
    runtime_state: Any = None,
) -> Dict[str, Any]:
    """
    Analyze intent, build an internal plan, validate whitelist + max steps,
    execute sequentially. Stops on first tool failure; no infinite retry.

    ``context`` may include:
      - ``intent``: ``error_recovery`` | ``user_request`` | ``vision_task``
      - ``task_id``: for status queries
      - ``steps``: optional explicit list of ``{tool, args, reason}`` (clamped to MAX_STEPS)
    """
    warnings: List[str] = []
    executed: List[Dict[str, Any]] = []
    final_state: Dict[str, Any] = {}
    session_id = (
        str(context.get("session_id")) if isinstance(context, dict) and context.get("session_id") else f"exec-{int(time.time() * 1000)}"
    )
    trace = ExecutionTrace(session_id=session_id)
    trace.start_trace(context if isinstance(context, dict) else {})

    if not isinstance(context, dict):
        out = {
            "success": False,
            "executed_steps": [],
            "final_state": {},
            "warnings": ["context must be a dict"],
            "error": "INVALID_CONTEXT",
        }
        trace.log_decision("validation", {"ok": False, "error": "INVALID_CONTEXT"})
        trace.end_trace(out)
        return out

    steps = _plan_from_context(context)
    trace.log_decision("plan_generated", {"step_count": len(steps), "steps": steps})
    if len(steps) > MAX_STEPS:
        warnings.append(f"plan truncated to {MAX_STEPS} steps")
        steps = steps[:MAX_STEPS]
        trace.log_decision("plan_truncated", {"max_steps": MAX_STEPS})

    for i, step in enumerate(steps):
        ok_meta, err = _validate_step(step)
        if not ok_meta:
            warnings.append(f"step {i} invalid: {err}")
            out = {
                "success": False,
                "executed_steps": executed,
                "final_state": final_state,
                "warnings": warnings,
                "error": err,
                "failed_at_index": i,
            }
            trace.log_decision("step_validation_failed", {"index": i, "error": err, "step": step})
            trace.end_trace(out)
            return out
        tool = str(step["tool"])
        args = _normalize_args(step.get("args"))
        fn = _TOOL_REGISTRY.get(tool)
        if fn is None:
            out = {
                "success": False,
                "executed_steps": executed,
                "final_state": final_state,
                "warnings": warnings,
                "error": f"unregistered tool: {tool}",
                "failed_at_index": i,
            }
            trace.log_decision("tool_registry_failed", {"index": i, "tool": tool})
            trace.end_trace(out)
            return out
        try:
            t0 = time.perf_counter()
            result = fn(args, runtime_state)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            trace.log_step_execution(tool, args, result if isinstance(result, dict) else {"value": result}, dt_ms)
        except Exception as e:  # noqa: BLE001 — containment
            logger.exception("tool_orchestrator: tool=%s failed", tool)
            executed.append(
                {"tool": tool, "args": args, "ok": False, "error": str(e), "reason": step.get("reason", "")}
            )
            out = {
                "success": False,
                "executed_steps": executed,
                "final_state": final_state,
                "warnings": warnings,
                "error": str(e),
                "failed_at_index": i,
            }
            trace.log_decision("step_exception", {"index": i, "tool": tool, "error": str(e)})
            trace.end_trace(out)
            return out
        step_ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
        executed.append(
            {
                "tool": tool,
                "args": args,
                "ok": step_ok,
                "result": result,
                "reason": step.get("reason", ""),
            }
        )
        final_state[tool] = result
        if not step_ok:
            out = {
                "success": False,
                "executed_steps": executed,
                "final_state": final_state,
                "warnings": warnings,
                "error": (result or {}).get("error", "TOOL_FAILED") if isinstance(result, dict) else "TOOL_FAILED",
                "failed_at_index": i,
            }
            trace.log_decision("step_failed", {"index": i, "tool": tool})
            trace.end_trace(out)
            return out

    out = {
        "success": True,
        "executed_steps": executed,
        "final_state": final_state,
        "warnings": warnings,
    }
    trace.end_trace(out)
    return out


__all__ = [
    "ALLOWED_TOOLS",
    "MAX_STEPS",
    "execute_intent",
]
