"""Stress + stability verification harness for the Industrial Digital Twin demo.

Runs three modes and prints a compact report. No architectural changes — pure
runtime verification via Flask test client.
"""
from __future__ import annotations

import os
import sys
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api import app, _RUNTIME_STATE  # type: ignore
import backend.runtime_state as rs_mod  # type: ignore

ALLOWED = {
    "queued",
    "validating",
    "processing_ocr",
    "parsing_layout",
    "building_graph",
    "rendering_scene",
    "finalizing",
    "done",
    "failed",
    "cancelled",
}
STAGE_ORDER = [
    "queued",
    "validating",
    "processing_ocr",
    "parsing_layout",
    "building_graph",
    "rendering_scene",
    "finalizing",
    "done",
]


def _post_upload(c, plan_name: str = "a.png", excel_name: str = "a.xlsx", plan_bytes: bytes = b"img", excel_bytes: bytes = b"xlsx") -> Dict[str, Any]:
    return c.post(
        "/api/upload",
        data={
            "plan_file": (BytesIO(plan_bytes), plan_name),
            "excel_file": (BytesIO(excel_bytes), excel_name),
        },
        content_type="multipart/form-data",
    )


def _wait_terminal(c, task_id: str, timeout_s: float = 8.0) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        r = c.get(f"/api/task/{task_id}")
        j = r.get_json() or {}
        last = j
        if j.get("status") in {"done", "failed", "cancelled"}:
            return j
        time.sleep(0.1)
    return last


def section(title: str) -> None:
    print("\n==== " + title + " ====")


def mode_a_normal_load(c) -> Dict[str, Any]:
    section("Mode A — normal load (concurrent uploads + repeated identical)")
    results: List[Dict[str, Any]] = []
    N = 12
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(_post_upload, c) for _ in range(N)]
        for f in as_completed(futures):
            r = f.result()
            j = r.get_json() or {}
            results.append({"status_code": r.status_code, "body": j})
    immediate_ok = all(
        x["status_code"] == 200 and (x["body"] or {}).get("status") == "queued" for x in results
    )
    states_seen: List[str] = []
    for x in results:
        tid = (x["body"] or {}).get("task_id")
        if not tid:
            continue
        term = _wait_terminal(c, tid)
        states_seen.append(term.get("status", "?"))
    # repeated identical inputs
    r1 = c.get("/api/pipeline")
    r2 = c.get("/api/pipeline")
    obs = c.get("/api/observability").get_json() or {}
    return {
        "uploads": N,
        "immediate_ok": immediate_ok,
        "terminal_states": states_seen,
        "pipeline1": r1.status_code,
        "pipeline2": r2.status_code,
        "cache_hit_rate": obs.get("cache_hit_rate"),
        "active_tasks": obs.get("active_tasks"),
    }


def mode_b_failure_injection(c) -> Dict[str, Any]:
    section("Mode B — failure injection")
    out: Dict[str, Any] = {}

    # B1: INVALID_EXCEL via /api/pipeline (sync structured error)
    pr = c.get("/api/pipeline")
    pj = pr.get_json() or {}
    out["invalid_excel_sync"] = {
        "status": pr.status_code,
        "code": (pj.get("error") or {}).get("code"),
        "stage": (pj.get("error") or {}).get("stage"),
    }

    # B2: Upload invalid files -> task terminal failed with stage preserved
    up = _post_upload(c).get_json() or {}
    tid = up.get("task_id")
    term = _wait_terminal(c, tid)
    err = term.get("error") or {}
    out["invalid_excel_async"] = {
        "status": term.get("status"),
        "code": err.get("code") if isinstance(err, dict) else None,
        "stage": err.get("stage") if isinstance(err, dict) else None,
    }

    # B3: Corrupted PDF -> returned immediately as structured error
    pdf_res = c.post(
        "/api/upload",
        data={"plan_file": (BytesIO(b"not-a-pdf"), "bad.pdf")},
        content_type="multipart/form-data",
    )
    pj = pdf_res.get_json() or {}
    out["corrupted_pdf"] = {
        "status": pdf_res.status_code,
        "code": (pj.get("error") or {}).get("code"),
        "stage": (pj.get("error") or {}).get("stage"),
    }

    # B4: Synthetic TIMEOUT by shrinking threshold for a new idle task
    orig_stuck = _RUNTIME_STATE._stuck_threshold_s
    orig_timeout = _RUNTIME_STATE._task_timeout_s
    try:
        _RUNTIME_STATE._stuck_threshold_s = 0.2
        _RUNTIME_STATE._task_timeout_s = 0.4
        tid = _RUNTIME_STATE.new_task("idle-sim")
        time.sleep(0.6)
        j = c.get(f"/api/task/{tid}").get_json() or {}
        out["timeout_injection"] = {
            "status": j.get("status"),
            "code": (j.get("error") or {}).get("code"),
        }
    finally:
        _RUNTIME_STATE._stuck_threshold_s = orig_stuck
        _RUNTIME_STATE._task_timeout_s = orig_timeout

    # B5: Synthetic STUCK by very small stuck threshold, but timeout large
    try:
        _RUNTIME_STATE._stuck_threshold_s = 0.2
        _RUNTIME_STATE._task_timeout_s = 60.0
        tid = _RUNTIME_STATE.new_task("idle-sim-2")
        time.sleep(0.4)
        j = c.get(f"/api/task/{tid}").get_json() or {}
        out["stuck_injection"] = {
            "status": j.get("status"),
            "code": (j.get("error") or {}).get("code"),
        }
    finally:
        _RUNTIME_STATE._stuck_threshold_s = orig_stuck
        _RUNTIME_STATE._task_timeout_s = orig_timeout

    # B6: Priority rule — both triggers, TIMEOUT must win
    try:
        _RUNTIME_STATE._stuck_threshold_s = 0.1
        _RUNTIME_STATE._task_timeout_s = 0.1
        tid = _RUNTIME_STATE.new_task("both-trigger")
        time.sleep(0.5)
        j = c.get(f"/api/task/{tid}").get_json() or {}
        out["priority_rule"] = {
            "status": j.get("status"),
            "code": (j.get("error") or {}).get("code"),
        }
    finally:
        _RUNTIME_STATE._stuck_threshold_s = orig_stuck
        _RUNTIME_STATE._task_timeout_s = orig_timeout

    return out


def mode_c_soak(c, duration_s: float = 20.0, interval_s: Tuple[float, float] = (0.05, 0.3)) -> Dict[str, Any]:
    section(f"Mode C — soak ({duration_s:.0f}s)")
    stop = time.time() + duration_s
    n_accepted = 0
    n_terminal = 0
    while time.time() < stop:
        res = _post_upload(c)
        if res.status_code == 200 and (res.get_json() or {}).get("success") is True:
            n_accepted += 1
        time.sleep(random.uniform(*interval_s))
    # drain: wait all tasks to terminal
    deadline = time.time() + 10.0
    while time.time() < deadline:
        with _RUNTIME_STATE._lock:
            active = sum(1 for r in _RUNTIME_STATE._tasks.values() if r.status in {"queued", "running"})
        if active == 0:
            break
        time.sleep(0.2)
    obs = c.get("/api/observability").get_json() or {}
    with _RUNTIME_STATE._lock:
        mem_tasks = len(_RUNTIME_STATE._tasks)
        mem_cache = len(_RUNTIME_STATE._cache)
    return {
        "accepted_uploads": n_accepted,
        "active_after_drain": obs.get("active_tasks"),
        "failed_tasks": obs.get("failed_tasks"),
        "completed_tasks": obs.get("completed_tasks"),
        "cache_hit_rate": obs.get("cache_hit_rate"),
        "worker_status": obs.get("worker_status"),
        "memory_tasks": mem_tasks,
        "memory_cache": mem_cache,
    }


def state_machine_walk() -> Dict[str, Any]:
    section("State machine walk (verify ordered progression)")
    visited: List[str] = []
    # simulate a happy-path walk by calling set_stage in order
    _RUNTIME_STATE._stuck_threshold_s = 60.0
    _RUNTIME_STATE._task_timeout_s = 180.0
    tid = _RUNTIME_STATE.new_task("walk")
    for s in ["validating", "processing_ocr", "parsing_layout", "building_graph", "rendering_scene", "finalizing"]:
        _RUNTIME_STATE.set_stage(tid, s, f"{s}…")
        rec = _RUNTIME_STATE.get_task(tid) or {}
        visited.append(rec.get("stage", "?"))
    _RUNTIME_STATE.update_task(tid, status="done", stage="done", message="ok")
    rec = _RUNTIME_STATE.get_task(tid) or {}
    visited.append(rec.get("stage", "?"))
    ok = visited == ["validating", "processing_ocr", "parsing_layout", "building_graph", "rendering_scene", "finalizing", "done"]
    return {"ordered": ok, "visited": visited}


def main() -> int:
    c = app.test_client()

    a = mode_a_normal_load(c)
    print(a)

    b = mode_b_failure_injection(c)
    print(b)

    sm = state_machine_walk()
    print(sm)

    soak_seconds = float(os.environ.get("SOAK_SECONDS", "15"))
    c_res = mode_c_soak(c, duration_s=soak_seconds)
    print(c_res)

    # Aggregate assertions — fail early if a core invariant breaks
    fails: List[str] = []
    if not a.get("immediate_ok"):
        fails.append("upload did not return immediately for all Mode A uploads")
    if a.get("pipeline1") != 400 and a.get("pipeline1") not in {200}:
        fails.append(f"/api/pipeline unexpected status: {a.get('pipeline1')}")
    if (b["invalid_excel_sync"].get("code") not in {"INVALID_EXCEL"}):
        fails.append("sync invalid excel did not map to INVALID_EXCEL")
    if (b["invalid_excel_async"].get("stage") not in STAGE_ORDER):
        fails.append("async failure stage not a valid stage")
    if (b["corrupted_pdf"].get("code") not in {"PIPELINE_ERROR"}) or (b["corrupted_pdf"].get("status") != 400):
        fails.append("corrupted pdf not rejected with structured 400 error")
    if (b["timeout_injection"].get("code") != "TIMEOUT"):
        fails.append("timeout injection did not produce TIMEOUT code")
    if (b["stuck_injection"].get("code") != "STUCK_DETECTED"):
        fails.append("stuck injection did not produce STUCK_DETECTED code")
    if (b["priority_rule"].get("code") != "TIMEOUT"):
        fails.append("priority rule failed: TIMEOUT must win over STUCK")
    if not sm.get("ordered"):
        fails.append(f"state machine order invalid: {sm.get('visited')}")
    if c_res.get("active_after_drain") not in (0, None):
        fails.append(f"active tasks leaked after drain: {c_res.get('active_after_drain')}")
    if c_res.get("memory_tasks", 0) > 50:
        fails.append(f"memory task storage unbounded: {c_res.get('memory_tasks')}")

    section("RESULT")
    if fails:
        for f in fails:
            print("FAIL -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
