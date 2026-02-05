from __future__ import annotations

import asyncio
import datetime as dt
import time
from collections.abc import Awaitable, Callable
from collections.abc import Mapping
from typing import TypeAlias

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobQueue
from app.metrics import (
    JOB_QUEUE_JOBS_TOTAL,
    JOB_QUEUE_PROCESSING_SECONDS,
    JOB_QUEUE_WAIT_SECONDS,
)
from app.settings import settings

Handler: TypeAlias = Callable[
    [Callable[[], AsyncSession], JobQueue], Awaitable[None]
]


async def claim_one_job(session: AsyncSession) -> JobQueue | None:
    """Claim one queued job using FOR UPDATE SKIP LOCKED."""

    # Transaction: claim a queued job using SKIP LOCKED (non-blocking)
    # We use raw SQL to leverage FOR UPDATE SKIP LOCKED reliably.
    row = await session.execute(text("""
            SELECT job_queue_uuid
            FROM job_queue
            WHERE status = 'queued' AND run_after <= now()
            ORDER BY run_after ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """))
    job_id = row.scalar_one_or_none()
    if job_id is None:
        return None

    job = await session.get(JobQueue, job_id)
    if job is None:
        return None
    job.status = "running"
    job.started_at = dt.datetime.now(dt.timezone.utc)
    job.attempt_count = int(job.attempt_count) + 1

    if settings.observability_metrics_enabled:
        try:
            wait_s = (job.started_at - job.run_after).total_seconds()
            if wait_s >= 0:
                JOB_QUEUE_WAIT_SECONDS.labels(job_type=job.job_type).observe(
                    wait_s
                )
        except Exception:  # noqa: BLE001
            # Never fail job claiming due to metrics.
            pass
    return job


async def run_worker_forever(
    session_factory: Callable[[], AsyncSession],
    handlers: Mapping[str, Handler],
    poll_interval_s: float = 1.0,
) -> None:
    """Continuously poll the queue and dispatch jobs to handlers."""
    while True:
        async with session_factory() as session:
            async with session.begin():
                job = await claim_one_job(session)

            if job is None:
                await asyncio.sleep(poll_interval_s)
                continue

            handler = handlers.get(job.job_type)
            if handler is None:
                async with session.begin():
                    job.status = "failed"
                    job.last_error = f"Unknown job_type: {job.job_type}"
                    job.finished_at = dt.datetime.now(dt.timezone.utc)
                continue

            started = time.perf_counter()
            try:
                await handler(session_factory, job)
                duration_s = time.perf_counter() - started
                async with session.begin():
                    job.status = "succeeded"
                    job.last_error = None
                    job.finished_at = dt.datetime.now(dt.timezone.utc)

                if settings.observability_metrics_enabled:
                    JOB_QUEUE_JOBS_TOTAL.labels(
                        job_type=job.job_type, outcome="succeeded"
                    ).inc()
                    JOB_QUEUE_PROCESSING_SECONDS.labels(
                        job_type=job.job_type, outcome="succeeded"
                    ).observe(duration_s)
            except Exception as e:  # noqa: BLE001
                duration_s = time.perf_counter() - started
                async with session.begin():
                    job.status = "failed"
                    job.last_error = str(e)
                    job.finished_at = dt.datetime.now(dt.timezone.utc)

                if settings.observability_metrics_enabled:
                    JOB_QUEUE_JOBS_TOTAL.labels(
                        job_type=job.job_type, outcome="failed"
                    ).inc()
                    JOB_QUEUE_PROCESSING_SECONDS.labels(
                        job_type=job.job_type, outcome="failed"
                    ).observe(duration_s)
