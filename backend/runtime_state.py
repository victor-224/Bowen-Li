"""Runtime task/caching state for stable async demo execution."""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional


def _files_signature(paths: Mapping[str, Optional[Path]]) -> str:
    h = hashlib.sha256()
    for key in sorted(paths.keys()):
        p = paths.get(key)
        h.update(key.encode("utf-8", errors="ignore"))
        if p is None:
            h.update(b"<none>")
            continue
        pp = Path(p)
        h.update(str(pp).encode("utf-8", errors="ignore"))
        try:
            st = pp.stat()
            h.update(str(int(st.st_mtime_ns)).encode("ascii"))
            h.update(str(int(st.st_size)).encode("ascii"))
        except FileNotFoundError:
            h.update(b"<missing>")
    return h.hexdigest()


@dataclass
class TaskRecord:
    task_id: str
    status: str
    stage: str
    progress: int
    message: str
    created_at: float
    updated_at: float
    error: Optional[str] = None
    error_code: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    events: list[Dict[str, Any]] = field(default_factory=list)
    cancelled: bool = False


_STAGE_ORDER = {
    "queued": 0,
    "validating": 1,
    "processing_ocr": 2,
    "parsing_layout": 3,
    "building_graph": 4,
    "rendering_scene": 5,
    "finalizing": 6,
    "done": 7,
    "failed": 8,
    "cancelled": 9,
}


def _stage_progress(stage: str) -> int:
    return {
        "queued": 0,
        "validating": 10,
        "processing_ocr": 25,
        "parsing_layout": 45,
        "building_graph": 65,
        "rendering_scene": 85,
        "finalizing": 95,
        "done": 100,
        "failed": 100,
        "cancelled": 100,
    }.get(stage, 0)


class RuntimeState:
    """Thread-safe in-memory runtime state for demo pipeline."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipeline-worker")
        self._tasks: Dict[str, TaskRecord] = {}
        self._latest_task_id: Optional[str] = None
        self._max_tasks: int = 20
        self._task_ttl_s: int = 600
        # Single deterministic cache by input signature.
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._completed_count: int = 0
        self._failed_count: int = 0
        self._cancelled_count: int = 0
        self._total_duration_ms: float = 0.0
        self._worker_status: str = "healthy"
        # Heartbeat/stuck/timeout thresholds (seconds).
        self._stuck_threshold_s: float = 60.0
        self._task_timeout_s: float = 180.0

    def _prune_tasks_unlocked(self) -> None:
        now = time.time()
        expired = [tid for tid, rec in self._tasks.items() if (now - rec.updated_at) > self._task_ttl_s]
        for tid in expired:
            self._tasks.pop(tid, None)
        if len(self._tasks) <= self._max_tasks:
            return
        ordered = sorted(self._tasks.values(), key=lambda x: x.updated_at)
        to_remove = len(self._tasks) - self._max_tasks
        for rec in ordered[:to_remove]:
            self._tasks.pop(rec.task_id, None)

    def new_task(self, message: str = "Queued") -> str:
        now = time.time()
        task_id = str(uuid.uuid4())
        rec = TaskRecord(
            task_id=task_id,
            status="queued",
            stage="queued",
            progress=0,
            message=message,
            created_at=now,
            updated_at=now,
        )
        rec.events.append({"time": now, "stage": "queued", "message": message})
        with self._lock:
            self._tasks[task_id] = rec
            self._latest_task_id = task_id
            self._prune_tasks_unlocked()
        return task_id

    def update_task(
        self,
        task_id: str,
        *,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        error_code: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                return
            if status is not None:
                rec.status = status
            if stage is not None:
                rec.stage = stage
                rec.progress = _stage_progress(stage)
                rec.events.append({"time": time.time(), "stage": stage, "message": message or rec.message})
            if progress is not None:
                rec.progress = max(0, min(100, int(progress)))
            if message is not None:
                rec.message = message
            if error is not None:
                rec.error = error
            if error_code is not None:
                rec.error_code = error_code
            if result is not None:
                rec.result = result
            if rec.status in {"done", "failed", "cancelled"} and rec.duration_ms is None:
                rec.duration_ms = max(0.0, (time.time() - rec.created_at) * 1000.0)
                self._total_duration_ms += rec.duration_ms
                if rec.status == "done":
                    self._completed_count += 1
                elif rec.status == "failed":
                    self._failed_count += 1
                else:
                    self._cancelled_count += 1
            rec.updated_at = time.time()
            self._prune_tasks_unlocked()

    def set_stage(self, task_id: str, stage: str, message: str) -> None:
        status = "running"
        if stage == "done":
            status = "done"
        elif stage == "failed":
            status = "failed"
        elif stage == "cancelled":
            status = "cancelled"
        self.update_task(task_id, status=status, stage=stage, message=message)

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                return False
            rec.cancelled = True
            rec.updated_at = time.time()
            rec.events.append({"time": rec.updated_at, "stage": "cancelled", "message": "Cancellation requested"})
            return True

    def is_cancelled(self, task_id: str) -> bool:
        with self._lock:
            rec = self._tasks.get(task_id)
            return bool(rec.cancelled) if rec else False

    def _enforce_stuck_and_timeout_unlocked(self, rec: TaskRecord) -> None:
        if rec.status not in {"queued", "running"}:
            return
        now = time.time()
        age_total = now - rec.created_at
        idle = now - rec.updated_at
        stuck = idle > self._stuck_threshold_s
        timed_out = age_total > self._task_timeout_s
        if not (stuck or timed_out):
            return
        rec.status = "failed"
        # keep last known pipeline stage for failure clarity
        rec.progress = 100
        rec.error = "Task exceeded allowed time" if timed_out else "No heartbeat update within threshold"
        rec.error_code = "TIMEOUT" if timed_out else "STUCK_DETECTED"
        rec.message = "Failed (timeout)" if timed_out else "Failed (stuck)"
        rec.duration_ms = max(0.0, (now - rec.created_at) * 1000.0)
        rec.events.append({"time": now, "stage": rec.stage, "message": rec.message})
        self._total_duration_ms += rec.duration_ms
        self._failed_count += 1

    def _enforce_all_unlocked(self) -> None:
        for rec in list(self._tasks.values()):
            self._enforce_stuck_and_timeout_unlocked(rec)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                return None
            self._enforce_stuck_and_timeout_unlocked(rec)
            return {
                "task_id": rec.task_id,
                "status": rec.status,
                "stage": rec.stage,
                "progress": rec.progress,
                "message": rec.message,
                "error": rec.error,
                "error_code": rec.error_code,
                "duration_ms": rec.duration_ms,
                "created_at": rec.created_at,
                "updated_at": rec.updated_at,
                "events": list(rec.events[-20:]),
            }

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None or rec.result is None:
                return None
            return dict(rec.result)

    def latest_task(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._latest_task_id is None:
                return None
            rec = self._tasks.get(self._latest_task_id)
            if rec is None:
                return None
            self._enforce_stuck_and_timeout_unlocked(rec)
            return {
                "task_id": rec.task_id,
                "status": rec.status,
                "stage": rec.stage,
                "progress": rec.progress,
                "message": rec.message,
                "error": rec.error,
                "error_code": rec.error_code,
                "duration_ms": rec.duration_ms,
                "created_at": rec.created_at,
                "updated_at": rec.updated_at,
            }

    def submit_pipeline_task(
        self,
        task_id: str,
        *,
        signature: str,
        builder: Callable[[], Dict[str, Any]],
    ) -> None:
        def _job() -> None:
            self.set_stage(task_id, "validating", "Validating files")
            try:
                if self.is_cancelled(task_id):
                    self.set_stage(task_id, "cancelled", "Task cancelled")
                    return
                self.set_stage(task_id, "processing_ocr", "Running OCR")
                if self.is_cancelled(task_id):
                    self.set_stage(task_id, "cancelled", "Task cancelled")
                    return
                self.set_stage(task_id, "parsing_layout", "Parsing layout")
                if self.is_cancelled(task_id):
                    self.set_stage(task_id, "cancelled", "Task cancelled")
                    return
                self.set_stage(task_id, "building_graph", "Building graph")
                if self.is_cancelled(task_id):
                    self.set_stage(task_id, "cancelled", "Task cancelled")
                    return
                self.set_stage(task_id, "rendering_scene", "Rendering scene payload")
                payload = builder()
                self.set_stage(task_id, "finalizing", "Finalizing")
                with self._lock:
                    self._cache[signature] = dict(payload)
                self.update_task(task_id, status="done", stage="done", message="Completed", result=payload)
            except Exception as e:  # noqa: BLE001 - structured error output
                # preserve last pipeline stage for failure clarity
                current = self.get_task(task_id) or {}
                last_stage = str(current.get("stage") or "validating")
                code = getattr(e, "code", None) or "PIPELINE_ERROR"
                self.update_task(
                    task_id,
                    status="failed",
                    stage=last_stage,
                    message="Failed",
                    error=str(e),
                    error_code=str(code),
                )

        self._executor.submit(_job)

    def get_cached_payload(
        self,
        signature: str,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            if signature in self._cache:
                self._cache_hits += 1
                return dict(self._cache[signature])
            self._cache_misses += 1
            return None

    def set_cached_payload(self, *, signature: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._cache[signature] = dict(payload)

    def clear_pipeline_cache(self) -> int:
        """Remove all cached pipeline payloads (e.g. after asset repair). Returns entries cleared."""
        with self._lock:
            n = len(self._cache)
            self._cache.clear()
            return n

    def build_signature(self, paths: Mapping[str, Optional[Path]]) -> str:
        return _files_signature(paths)

    def observability(self) -> Dict[str, Any]:
        with self._lock:
            self._enforce_all_unlocked()
            active = sum(1 for r in self._tasks.values() if r.status in {"queued", "running"})
            completed = self._completed_count
            failed = self._failed_count
            total_cache = self._cache_hits + self._cache_misses
            cache_hit_rate = float(self._cache_hits / total_cache) if total_cache > 0 else 0.0
            avg_duration = float(self._total_duration_ms / completed) if completed > 0 else 0.0
            return {
                "active_tasks": active,
                "completed_tasks": completed,
                "failed_tasks": failed,
                "cancelled_tasks": self._cancelled_count,
                "cache_hit_rate": round(cache_hit_rate, 4),
                "avg_task_duration": round(avg_duration, 3),
                "memory_estimate": f"tasks={len(self._tasks)} cache={len(self._cache)}",
                "worker_status": self._worker_status,
            }

