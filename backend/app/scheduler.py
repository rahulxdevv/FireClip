"""Small in-process scheduler used when Redis/ARQ is not configured.

It enqueues due scheduled posts and removes stale temp files. With ARQ the same
work is done by worker cron jobs (see app/worker.py).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select

from .config import settings
from .database import session_scope
from .jobs import create_pipeline_job, enqueue
from .models import PublishingJob

logger = logging.getLogger("fireclip.scheduler")
_stop = threading.Event()


def _tick() -> None:
    now = datetime.now(timezone.utc)
    with session_scope() as db:
        due = list(
            db.scalars(
                select(PublishingJob).where(
                    PublishingJob.status == "scheduled",
                    PublishingJob.scheduled_for.is_not(None),
                    PublishingJob.scheduled_for <= now,
                )
            )
        )
        for job in due:
            job.status = "queued"
            pipeline_job = create_pipeline_job(
                db,
                workspace_id=job.workspace_id,
                video_id=None,
                kind="publishing",
                task_name="publish_video",
                payload={"publishing_job_id": job.id},
            )
            enqueue(pipeline_job.id)
            logger.info("Enqueued due publish job %s", job.id)
    # Temp files older than a day are safe to drop.
    cutoff = time.time() - 86400
    for path in (settings.data_dir / "tmp").glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


def _loop() -> None:
    while not _stop.wait(30):
        try:
            _tick()
        except Exception:  # pragma: no cover - never kill the scheduler
            logger.exception("Scheduler tick failed")


def start_inline_scheduler() -> threading.Thread:
    thread = threading.Thread(target=_loop, name="fireclip-scheduler", daemon=True)
    thread.start()
    return thread


def stop_scheduler() -> None:
    _stop.set()
