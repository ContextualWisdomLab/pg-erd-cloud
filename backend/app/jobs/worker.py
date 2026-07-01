from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from collections.abc import Awaitable, Callable
from collections.abc import Mapping
from typing import TypeAlias

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobQueue
from app.jobs.valkey_queue import (
    pop_due_job_signal,
    valkey_queue_enabled,
)
from app.metrics import (
    JOB_QUEUE_JOBS_TOTAL,
    JOB_QUEUE_PROCESSING_SECONDS,
    JOB_QUEUE_WAIT_SECONDS,
)
from app.settings import settings

_logger = logging.getLogger(__name__)

Handler: TypeAlias = Callable[
    [Callable[[], AsyncSession], JobQueue], Awaitable[None]
]


def _mark_job_running(job: JobQueue) -> JobQueue:
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
            _logger.debug(
                "job queue wait metric observation failed", exc_info=True
            )
    return job


async def _claim_job_by_id(
    session: AsyncSession,
    job_queue_uuid: object,
) -> JobQueue | None:
    """Claim a specific queued job if it is due and not already locked."""

    row = await session.execute(
        text("""
            SELECT job_queue_uuid
            FROM job_queue
            WHERE
              job_queue_uuid = :job_queue_uuid
              AND status = 'queued'
              AND run_after <= now()
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """),
        {"job_queue_uuid": job_queue_uuid},
    )
    job_id = row.scalar_one_or_none()
    if job_id is None:
        return None

    job = await session.get(JobQueue, job_id)
    if job is None:
        return None
    return _mark_job_running(job)


async def claim_one_job(session: AsyncSession) -> JobQueue | None:
    """Claim one queued job using FOR UPDATE SKIP LOCKED."""

    if valkey_queue_enabled():
        signaled_job_id = await pop_due_job_signal()
        if signaled_job_id is not None:
            job = await _claim_job_by_id(session, signaled_job_id)
            if job is not None:
                return job

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
    return _mark_job_running(job)


def _publish_job_metrics(
    *,
    job_type: str,
    outcome: str,
    duration_s: float | None,
) -> None:
    """Publish job metrics (best-effort) when metrics are enabled."""
    if not settings.observability_metrics_enabled:
        return

    JOB_QUEUE_JOBS_TOTAL.labels(job_type=job_type, outcome=outcome).inc()
    if duration_s is not None:
        JOB_QUEUE_PROCESSING_SECONDS.labels(
            job_type=job_type,
            outcome=outcome,
        ).observe(duration_s)


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

                _publish_job_metrics(
                    job_type=job.job_type,
                    outcome="succeeded",
                    duration_s=duration_s,
                )
            except Exception as e:  # noqa: BLE001
                duration_s = time.perf_counter() - started
                async with session.begin():
                    job.status = "failed"
                    job.last_error = str(e)
                    job.finished_at = dt.datetime.now(dt.timezone.utc)

                _publish_job_metrics(
                    job_type=job.job_type,
                    outcome="failed",
                    duration_s=duration_s,
                )
