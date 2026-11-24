"""ARQ worker entrypoint: `python -m app.worker`."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from .config import settings
from .jobs import load_tasks, run_task_async, set_arq_pool
from .models import PublishingJob

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")


async def enqueue_due_publishes(ctx) -> None:
    from .database import session_scope
    from .jobs import create_pipeline_job
    from .jobs import enqueue

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
            await ctx["redis"].enqueue_job("run_task", pipeline_job.id, _queue_name="fireclip")


async def enqueue_due_live_recordings(ctx) -> None:
    from .services.live import check_due_live_streams

    await asyncio.to_thread(check_due_live_streams)


async def startup(ctx) -> None:
    load_tasks()
    # Chained tasks (transcribe -> analyse -> render) enqueue through this pool.
    set_arq_pool(ctx["redis"], asyncio.get_running_loop())
    logging.getLogger("fireclip.worker").info("FireClip worker ready")



class WorkerSettings:
    functions = [run_task_async]
    cron_jobs = [
        cron(enqueue_due_publishes, minute=set(range(60)), run_at_startup=True),
        cron(enqueue_due_live_recordings, minute=set(range(60)), run_at_startup=True),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url or "redis://localhost:6379")
    queue_name = "fireclip"
    max_jobs = max(1, settings.worker_concurrency)
    job_timeout = 3600
    max_tries = 2
    on_startup = startup
    keep_result = 3600


def main() -> None:
    from arq import run_worker

    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
