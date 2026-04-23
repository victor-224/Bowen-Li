"""Phase C: lightweight metrics / tracing / audit observability."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metrics_path(runtime_dir: Path) -> Path:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / "metrics.json"


def _audit_path(runtime_dir: Path) -> Path:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / "audit.log"


def start_trace(operation: str) -> Dict[str, Any]:
    return {
        "trace_id": str(uuid.uuid4()),
        "operation": operation,
        "started_at": _utc_now(),
        "_t0": time.perf_counter(),
    }


def finish_trace(trace: Mapping[str, Any], *, status: str = "ok") -> Dict[str, Any]:
    elapsed_ms = (time.perf_counter() - float(trace.get("_t0", time.perf_counter()))) * 1000.0
    return {
        "trace_id": trace.get("trace_id"),
        "operation": trace.get("operation"),
        "started_at": trace.get("started_at"),
        "finished_at": _utc_now(),
        "elapsed_ms": round(elapsed_ms, 3),
        "status": status,
    }


def _read_metrics(runtime_dir: Path) -> Dict[str, Any]:
    path = _metrics_path(runtime_dir)
    if not path.is_file():
        return {"counters": {}, "latency_ms": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"counters": {}, "latency_ms": {}}


def _write_metrics(runtime_dir: Path, data: Mapping[str, Any]) -> None:
    _metrics_path(runtime_dir).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def observe_operation(runtime_dir: Path, trace_result: Mapping[str, Any]) -> None:
    metrics = _read_metrics(runtime_dir)
    op = str(trace_result.get("operation", "unknown"))
    status = str(trace_result.get("status", "ok"))
    elapsed = float(trace_result.get("elapsed_ms", 0.0))

    counters = metrics.setdefault("counters", {})
    counters[op] = int(counters.get(op, 0)) + 1
    counters[f"{op}:{status}"] = int(counters.get(f"{op}:{status}", 0)) + 1

    latency = metrics.setdefault("latency_ms", {})
    cur = latency.get(op, {"count": 0, "sum": 0.0, "avg": 0.0, "last": 0.0})
    cur["count"] = int(cur.get("count", 0)) + 1
    cur["sum"] = float(cur.get("sum", 0.0)) + elapsed
    cur["avg"] = round(cur["sum"] / max(cur["count"], 1), 3)
    cur["last"] = round(elapsed, 3)
    latency[op] = cur

    _write_metrics(runtime_dir, metrics)


def audit_event(runtime_dir: Path, event: str, payload: Optional[Mapping[str, Any]] = None) -> None:
    record = {"time": _utc_now(), "event": event, "payload": dict(payload or {})}
    with _audit_path(runtime_dir).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_observability(runtime_dir: Path) -> Dict[str, Any]:
    metrics = _read_metrics(runtime_dir)
    audit_file = _audit_path(runtime_dir)
    audit_tail = []
    if audit_file.is_file():
        try:
            lines = audit_file.read_text(encoding="utf-8").splitlines()
            for line in lines[-50:]:
                if line.strip():
                    audit_tail.append(json.loads(line))
        except Exception:
            audit_tail = []
    return {"metrics": metrics, "audit_tail": audit_tail}
