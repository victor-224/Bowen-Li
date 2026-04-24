"""Spatial truth ledger for contract-audit observability."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


_LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime" / "spatial_truth_ledger.jsonl"
SPATIAL_TRUTH_LEDGER_FILE = _LEDGER_PATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, doc: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    except OSError:
        # Observability-only path: never interrupt runtime.
        return


def validate_contract_usage(
    contract: Dict[str, Any] | None,
    scene_input_source: str,
    used_in_scene: bool = False,
) -> Dict[str, Any]:
    """Validate whether scene input obeys spatial contract intent."""
    c = contract if isinstance(contract, dict) else {}
    source = str(scene_input_source or "unknown")
    mode = str(c.get("spatial_mode") or "")
    scene_allowed = bool(c.get("scene_allowed"))

    if not c and used_in_scene:
        return {"bypass_detected": True, "violation_type": "CONTRACT_IGNORED"}
    if source == "cluster_estimate" and scene_allowed:
        return {"bypass_detected": True, "violation_type": "DIRECT_CLUSTER_USAGE"}
    if mode == "VISUAL_ONLY" and used_in_scene:
        return {"bypass_detected": True, "violation_type": "VISUAL_ONLY_SCENE_USAGE"}
    return {"bypass_detected": False, "violation_type": "NONE"}


def log_spatial_event(event: Dict[str, Any]) -> None:
    """Append one spatial audit event to JSONL ledger."""
    if not isinstance(event, dict):
        return
    rec = {
        "timestamp": event.get("timestamp") or _now_iso(),
        "stage": str(event.get("stage") or "unknown"),
        "source": str(event.get("source") or "unknown"),
        "contract_mode": str(event.get("contract_mode") or "DEGRADED"),
        "scene_allowed": bool(event.get("scene_allowed")),
        "used_in_scene": bool(event.get("used_in_scene")),
        "bypass_detected": bool(event.get("bypass_detected")),
        "reason": str(event.get("reason") or ""),
    }
    if "violation_type" in event:
        rec["violation_type"] = str(event.get("violation_type") or "NONE")
    _append_jsonl(_LEDGER_PATH, rec)


def spatial_truth_summary(limit: int = 200) -> Dict[str, Any]:
    """Compact status envelope for API payloads."""
    if not _LEDGER_PATH.is_file():
        return {
            "spatial_truth_status": "CLEAN",
            "bypass_detected": False,
            "last_violation": "",
            "contract_history_available": False,
        }
    try:
        lines: List[str] = _LEDGER_PATH.read_text(encoding="utf-8").splitlines()[-max(1, limit) :]
    except OSError:
        return {
            "spatial_truth_status": "WARNING",
            "bypass_detected": False,
            "last_violation": "LEDGER_READ_ERROR",
            "contract_history_available": False,
        }

    status = "CLEAN"
    bypass = False
    last_violation = ""
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if bool(rec.get("bypass_detected")):
            bypass = True
            status = "VIOLATION"
            last_violation = str(rec.get("violation_type") or "UNKNOWN")
        elif status == "CLEAN" and str(rec.get("contract_mode") or "").upper() in {"DEGRADED", "VISUAL_ONLY"}:
            status = "WARNING"
    return {
        "spatial_truth_status": status,
        "bypass_detected": bypass,
        "last_violation": last_violation,
        "contract_history_available": True,
    }


def summarize_truth_status(_runtime_dir: Optional[Path] = None, *, limit: int = 200) -> Dict[str, Any]:
    """Backwards-compatible wrapper expected by API integration."""
    return spatial_truth_summary(limit=limit)


def get_spatial_truth_status(*, limit: int = 200) -> Dict[str, Any]:
    """Alias used by smoke/debug scripts."""
    return spatial_truth_summary(limit=limit)


__all__ = [
    "SPATIAL_TRUTH_LEDGER_FILE",
    "get_spatial_truth_status",
    "log_spatial_event",
    "spatial_truth_summary",
    "summarize_truth_status",
    "validate_contract_usage",
]
