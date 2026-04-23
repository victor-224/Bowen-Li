"""Runtime task and pipeline cache state for stable local demos."""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
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
    progress: int
    message: str
    created_at: float
    updated_at: float
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class RuntimeState:
    """Thread-safe in-memory runtime state for demo pipeline."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipeline-worker")
        self._tasks: Dict[str, TaskRecord] = {}
        self._latest_task_id: Optional[str] = None
        self._cache_payload: Optional[Dict[str, Any]] = None
        self._cache_signature: Optional[str] = None
        self._cache_at: float = 0.0
        self._cache_ttl_s: int = 30
        self._max_tasks: int = 64

    def _prune_tasks_unlocked(self) -> None:
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
            progress=0,
            message=message,
            created_at=now,
            updated_at=now,
        )
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
        progress: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                return
            if status is not None:
                rec.status = status
            if progress is not None:
                rec.progress = max(0, min(100, int(progress)))
            if message is not None:
                rec.message = message
            if error is not None:
                rec.error = error
            if result is not None:
                rec.result = result
            rec.updated_at = time.time()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                return None
            return {
                "task_id": rec.task_id,
                "status": rec.status,
                "progress": rec.progress,
                "message": rec.message,
                "error": rec.error,
                "created_at": rec.created_at,
                "updated_at": rec.updated_at,
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
            return {
                "task_id": rec.task_id,
                "status": rec.status,
                "progress": rec.progress,
                "message": rec.message,
                "error": rec.error,
                "created_at": rec.created_at,
                "updated_at": rec.updated_at,
            }

    def submit_pipeline_task(
        self,
        task_id: str,
        *,
        input_signature: str,
        builder: Callable[[], Dict[str, Any]],
    ) -> None:
        def _job() -> None:
            self.update_task(task_id, status="running", progress=10, message="Preparing pipeline")
            try:
                self.update_task(task_id, progress=25, message="Running OCR and scene generation")
                payload = builder()
                self.update_task(task_id, progress=90, message="Finalizing output")
                with self._lock:
                    self._cache_payload = payload
                    self._cache_signature = input_signature
                    self._cache_at = time.time()
                self.update_task(task_id, status="done", progress=100, message="Completed", result=payload)
            except Exception as e:  # noqa: BLE001 - structured error output
                self.update_task(task_id, status="error", progress=100, message="Failed", error=str(e))

        self._executor.submit(_job)

    def get_cached_payload(self, input_signature: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._cache_payload is None:
                return None
            if self._cache_signature != input_signature:
                return None
            if (time.time() - self._cache_at) > self._cache_ttl_s:
                return None
            return dict(self._cache_payload)

    def set_cached_payload(self, input_signature: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._cache_payload = dict(payload)
            self._cache_signature = input_signature
            self._cache_at = time.time()

    def build_signature(self, paths: Mapping[str, Optional[Path]]) -> str:
        return _files_signature(paths)

