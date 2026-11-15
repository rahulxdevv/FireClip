"""Background job plumbing.

Production uses Redis + ARQ (see app/worker.py). If Redis is not configured the
API falls back to an in-process thread pool so the whole product still works
locally. Both paths execute the same task callables and record the same
PipelineJob state, so the UI is identical.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select

from .config import settings
from .database import session_scope
from .models import Notification, PipelineJob, SourceVideo

logger = logging.getLogger("fireclip.jobs")

TaskCallable = Callable[["JobReporter"], None]

TASKS: dict[str, TaskCallable] = {}


def task(name: str):
    def decorator(fn: TaskCallable) -> TaskCallable:
        TASKS[name] = fn
        return fn

    return decorator


def load_tasks() -> None:
    """Import task modules so decorators register callables."""
    from . import tasks  # noqa: F401


def create_pipeline_job(
    db,
    *,
    workspace_id: str,
    video_id: str | None,
    kind: str,
    task_name: str,
    payload: dict[str, Any] | None = None,
) -> PipelineJob:
    load_tasks()
    if task_name not in TASKS:
        raise ValueError(f"Unknown task '{task_name}'")
    job = PipelineJob(
        workspace_id=workspace_id,
        video_id=video_id,
        kind=kind,
        task_name=task_name,
        payload=payload or {},
        status="queued",
        stage="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def enqueue(job_id: str) -> None:
    load_tasks()
    if settings.use_arq and _arq_pool is not None:
        coro = _arq_pool.enqueue_job("run_task", job_id, _queue_name="fireclip")
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is not None:
            # Already on an event loop: schedule without blocking it.
            running.create_task(coro)
            return
        loop = _arq_loop
        if loop is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=15)
                return
            except Exception:  # pragma: no cover - redis outage
                logger.exception("ARQ enqueue failed; running job inline")
        else:
            coro.close()
            logger.warning("ARQ queue is unavailable; running job inline")
    _executor.submit(_run_job_sync, job_id)


_executor = ThreadPoolExecutor(
    max_workers=max(1, settings.worker_concurrency), thread_name_prefix="fireclip-job"
)
_arq_pool = None
_arq_loop: asyncio.AbstractEventLoop | None = None


def set_arq_pool(pool, loop: asyncio.AbstractEventLoop | None = None) -> None:
    """Register the ARQ pool and the loop that owns its Redis connection.

    ARQ is async-only. API handlers and workers call ``enqueue`` from sync
    threads, so the coroutine is scheduled on the loop that created the pool.
    Without this, enqueueing silently does nothing and jobs stay queued forever.
    """
    global _arq_pool, _arq_loop
    _arq_pool = pool
    _arq_loop = loop


class JobReporter:
    """Progress/update handle passed to tasks."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.cancelled = False
        self._last_pct = -1.0

    def _load(self, db) -> PipelineJob | None:
        return db.get(PipelineJob, self.job_id)

    def progress(self, pct: float, stage: str | None = None) -> None:
        pct = max(0.0, min(100.0, pct))
        if abs(pct - self._last_pct) < 1 and stage is None:
            return
        self._last_pct = pct
        with session_scope() as db:
            job = self._load(db)
            if not job:
                raise RuntimeError("Job disappeared")
            if job.status == "cancelled":
                self.cancelled = True
                raise JobCancelled()
            job.progress = pct
            job.status = "running"
            if stage:
                job.stage = stage
            if not job.started_at:
                job.started_at = datetime.now(timezone.utc)
            if job.video_id:
                video = db.get(SourceVideo, job.video_id)
                if video:
                    video.progress = pct
                    if stage:
                        video.status = stage if stage in _VIDEO_STAGES else video.status

    def stage(self, stage: str, status: str | None = None) -> None:
        with session_scope() as db:
            job = self._load(db)
            if not job:
                return
            job.stage = stage
            if status:
                job.status = status
            if job.video_id:
                video = db.get(SourceVideo, job.video_id)
                if video and status in {"running", "queued"}:
                    video.status = stage

    def check_cancelled(self) -> None:
        if self.cancelled:
            raise JobCancelled()
        with session_scope() as db:
            job = self._load(db)
            if job and job.status == "cancelled":
                self.cancelled = True
                raise JobCancelled()

    @property
    def payload(self) -> dict:
        with session_scope() as db:
            job = self._load(db)
            return dict(job.payload or {}) if job else {}


class JobCancelled(Exception):
    pass


_VIDEO_STAGES = {
    "downloading",
    "probing",
    "transcribing",
    "analyzing",
    "rendering",
    "preparing",
}

TERMINAL = {"completed", "failed", "cancelled"}


def _run_job_sync(job_id: str, attempt: int = 1) -> None:
    load_tasks()
    with session_scope() as db:
        job = db.get(PipelineJob, job_id)
        if not job or job.status in TERMINAL:
            return
        job.status = "running"
        job.started_at = job.started_at or datetime.now(timezone.utc)
        job.attempts = attempt
        task_name = job.task_name
        workspace_id = job.workspace_id
        user_notified = bool(job.payload.get("notify", True))

    reporter = JobReporter(job_id)
    started = time.monotonic()
    try:
        TASKS[task_name](reporter)
    except JobCancelled:
        _finish(job_id, "cancelled", "Job cancelled by user")
        return
    except Exception as exc:  # noqa: BLE001 - reported to the user verbatim
        logger.error("Job %s (%s) failed: %s\n%s", job_id, task_name, exc, traceback.format_exc())
        if attempt < 2 and _retryable(exc):
            time.sleep(2)
            _run_job_sync(job_id, attempt + 1)
            return
        _finish(job_id, "failed", f"{type(exc).__name__}: {exc}", workspace_id, user_notified)
        return
    _finish(job_id, "completed", None, workspace_id, user_notified, time.monotonic() - started)


def _retryable(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("timeout", "temporarily", "connection", "429", "503"))


def _finish(
    job_id: str,
    status: str,
    error: str | None,
    workspace_id: str | None = None,
    notify_user: bool = True,
    elapsed: float | None = None,
) -> None:
    with session_scope() as db:
        job = db.get(PipelineJob, job_id)
        if not job:
            return
        if job.status == "cancelled" and status != "cancelled":
            return
        job.status = status
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = error
        if status == "completed":
            job.progress = 100.0
        if status == "cancelled":
            job.stage = "cancelled"
        if job.video_id and status in {"failed", "cancelled"}:
            video = db.get(SourceVideo, job.video_id)
            if video:
                video.status = "error" if status == "failed" else "ready"
                if status == "failed":
                    video.error_message = error
        if notify_user and workspace_id:
            title = {
                "completed": "Pipeline finished",
                "failed": "Pipeline failed",
                "cancelled": "Pipeline cancelled",
            }[status]
            db.add(
                Notification(
                    workspace_id=workspace_id,
                    user_id=None,
                    type="success" if status == "completed" else "error",
                    title=title,
                    body=(error or f"{job.kind} completed successfully.")[:900],
                )
            )


async def run_task_async(_ctx, job_id: str) -> None:
    """ARQ entrypoint."""
    import asyncio

    await asyncio.to_thread(_run_job_sync, job_id)


def cancel_job(db, job_id: str, workspace_id: str) -> bool:
    job = db.get(PipelineJob, job_id)
    if not job or job.workspace_id != workspace_id:
        return False
    if job.status in TERMINAL:
        return False
    job.status = "cancelled"
    job.stage = "cancelled"
    job.finished_at = datetime.now(timezone.utc)
    job.error_message = "Cancelled by user"
    db.commit()
    return True


def recover_interrupted_jobs() -> int:
    """Mark jobs left running by a crash/restart as failed (accurate status)."""
    fixed = 0
    with session_scope() as db:
        for job in db.scalars(select(PipelineJob).where(PipelineJob.status.in_(["running", "queued"]))):
            job.status = "failed"
            job.stage = "interrupted"
            job.error_message = "Interrupted by a server restart. Please retry."
            job.finished_at = datetime.now(timezone.utc)
            fixed += 1
        for video in db.scalars(
            select(SourceVideo).where(SourceVideo.status.in_(["downloading", "probing", "transcribing", "analyzing"]))
        ):
            video.status = "error"
            video.error_message = "Interrupted by a server restart. Please retry."
    return fixed
