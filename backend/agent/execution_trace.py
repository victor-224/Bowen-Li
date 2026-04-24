"""Passive execution tracing for tool orchestration sessions.

Non-intrusive by design:
  - No pipeline/task mutation
  - No exceptions propagated to callers
  - Lightweight JSONL append
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_LOCK = threading.Lock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _trace_file() -> Path:
    return _repo_root() / "data" / "runtime" / "execution_trace.jsonl"


def _iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class ExecutionTrace:
    def __init__(self, session_id: str):
        self.session_id = str(session_id)
        self._started_at: float = 0.0
        self._trace: Dict[str, Any] = {
            "session_id": self.session_id,
            "intent": "",
            "model_router": "",
            "started_at": "",
            "decisions": [],
            "steps": [],
            "final_result": {},
            "status": "unknown",
            "warnings": [],
        }

    def start_trace(self, context: dict) -> None:
        try:
            now = time.time()
            self._started_at = now
            ctx = context if isinstance(context, dict) else {}
            self._trace["started_at"] = _iso_utc(now)
            self._trace["intent"] = str(ctx.get("intent") or ctx.get("type") or "user_request")
            self._trace["model_router"] = str(
                ctx.get("model_router") or ctx.get("model") or ctx.get("ai_model") or ""
            )
            self._trace["input_context"] = ctx
        except Exception:
            return

    def log_decision(self, stage: str, data: dict) -> None:
        try:
            entry = {
                "ts": _iso_utc(time.time()),
                "stage": str(stage),
                "data": data if isinstance(data, dict) else {"value": str(data)},
            }
            self._trace["decisions"].append(entry)
        except Exception:
            return

    def log_step_execution(self, tool: str, input: dict, output: dict, duration_ms: float) -> None:
        try:
            entry = {
                "tool": str(tool),
                "input": input if isinstance(input, dict) else {},
                "output": output if isinstance(output, dict) else {"value": output},
                "duration_ms": float(duration_ms),
            }
            self._trace["steps"].append(entry)
        except Exception:
            return

    def end_trace(self, result: dict) -> None:
        try:
            now = time.time()
            self._trace["ended_at"] = _iso_utc(now)
            self._trace["duration_ms"] = max(0.0, (now - self._started_at) * 1000.0)
            if isinstance(result, dict):
                self._trace["final_result"] = result
                self._trace["status"] = "success" if bool(result.get("success")) else "failed"
                self._trace["warnings"] = list(result.get("warnings") or [])
            else:
                self._trace["final_result"] = {"value": result}
                self._trace["status"] = "failed"
            self._append_jsonl(self._trace)
        except Exception:
            return

    @staticmethod
    def _append_jsonl(doc: Dict[str, Any]) -> None:
        p = _trace_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(doc, ensure_ascii=False, default=str) + "\n"
        with _LOCK:
            with p.open("a", encoding="utf-8") as f:
                f.write(line)

