"""Queue regression tests.

ARQ's enqueue_job is async. The API and worker call enqueue() from sync
threads, so the coroutine must be scheduled on the loop that owns the Redis
pool. If this regresses, Docker deployments show queued jobs forever.
"""
from __future__ import annotations

import asyncio

from app import jobs


class FakePool:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def enqueue_job(self, function: str, job_id: str, *, _queue_name: str):
        self.calls.append((function, job_id, _queue_name))
        return object()


def test_enqueue_schedules_on_arq_pool(monkeypatch):
    fake = FakePool()

    async def scenario() -> None:
        jobs.set_arq_pool(fake, asyncio.get_running_loop())
        jobs.enqueue("job-123")
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    monkeypatch.setattr(jobs.settings, "job_runner", "arq")
    monkeypatch.setattr(jobs.settings, "redis_url", "redis://localhost:6379/0")
    try:
        asyncio.run(scenario())
    finally:
        jobs.set_arq_pool(None)

    assert fake.calls == [("run_task", "job-123", "fireclip")]
