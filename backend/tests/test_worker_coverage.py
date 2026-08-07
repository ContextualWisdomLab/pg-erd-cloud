"""Deterministic coverage for queue claiming, dispatch, and worker metrics."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any
import uuid

import pytest

from app.jobs import worker
from app.settings import settings


class _Result:
    """SQLAlchemy-like result carrying one optional scalar identifier."""

    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        """Return the configured scalar result."""
        return self.value


class _Session:
    """Async session double with queued query and model lookup results."""

    def __init__(
        self,
        *,
        scalar_values: list[object | None] | None = None,
        models: dict[object, object] | None = None,
    ) -> None:
        self.scalar_values = list(scalar_values or [])
        self.models = dict(models or {})
        self.execute_parameters: list[dict[str, object] | None] = []
        self.begin_calls = 0

    async def __aenter__(self) -> "_Session":
        """Enter the worker-owned session context."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Exit without suppressing failures."""
        return None

    def begin(self) -> "_Transaction":
        """Return one transaction context and record its use."""
        self.begin_calls += 1
        return _Transaction()

    async def execute(
        self,
        _statement: object,
        parameters: dict[str, object] | None = None,
    ) -> _Result:
        """Return the next configured query result and capture bind values."""
        self.execute_parameters.append(parameters)
        if not self.scalar_values:
            raise AssertionError("unexpected database query")
        return _Result(self.scalar_values.pop(0))

    async def get(self, _model: object, key: object) -> object | None:
        """Return a model object by its queue identifier."""
        return self.models.get(key)


class _Transaction:
    """No-op async transaction context."""

    async def __aenter__(self) -> "_Transaction":
        """Enter the transaction."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Exit the transaction."""
        return None


class _Metric:
    """Prometheus-like metric recording labels, observations, and increments."""

    def __init__(self, *, fail_observe: bool = False) -> None:
        self.fail_observe = fail_observe
        self.label_calls: list[dict[str, str]] = []
        self.observations: list[float] = []
        self.increment_calls = 0

    def labels(self, **labels: str) -> "_Metric":
        """Record metric labels and return the bound metric."""
        self.label_calls.append(labels)
        return self

    def observe(self, value: float) -> None:
        """Record an observation or raise the configured synthetic failure."""
        if self.fail_observe:
            raise RuntimeError("synthetic metrics failure")
        self.observations.append(value)

    def inc(self) -> None:
        """Record one counter increment."""
        self.increment_calls += 1


class _StopWorker(RuntimeError):
    """Sentinel used to terminate the otherwise infinite worker loop in tests."""


def _job(*, job_type: str = "snapshot", run_after_delta: float = -2.0) -> Any:
    """Return a mutable production-shaped queue record for worker tests."""
    now = dt.datetime.now(dt.timezone.utc)
    return SimpleNamespace(
        job_queue_uuid=uuid.uuid4(),
        job_type=job_type,
        status="queued",
        run_after=now + dt.timedelta(seconds=run_after_delta),
        started_at=None,
        finished_at=None,
        attempt_count=0,
        last_error=None,
    )


def test_mark_job_running_updates_state_without_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claim a job and increment its attempt counter when metrics are disabled."""
    monkeypatch.setattr(settings, "observability_metrics_enabled", False)
    job = _job()

    assert worker._mark_job_running(job) is job
    assert job.status == "running"
    assert job.started_at is not None
    assert job.attempt_count == 1


def test_mark_job_running_observes_nonnegative_wait_and_ignores_metric_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Emit queue wait when valid while containing telemetry implementation failures."""
    monkeypatch.setattr(settings, "observability_metrics_enabled", True)
    wait_metric = _Metric()
    monkeypatch.setattr(worker, "JOB_QUEUE_WAIT_SECONDS", wait_metric)
    job = _job(run_after_delta=-3.0)

    worker._mark_job_running(job)

    assert wait_metric.label_calls == [{"job_type": "snapshot"}]
    assert len(wait_metric.observations) == 1
    assert wait_metric.observations[0] >= 0

    failing_metric = _Metric(fail_observe=True)
    monkeypatch.setattr(worker, "JOB_QUEUE_WAIT_SECONDS", failing_metric)
    second = _job(run_after_delta=-1.0)
    assert worker._mark_job_running(second) is second
    assert second.status == "running"


def test_mark_job_running_skips_negative_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not publish a negative wait duration for a future-due synthetic job."""
    monkeypatch.setattr(settings, "observability_metrics_enabled", True)
    wait_metric = _Metric()
    monkeypatch.setattr(worker, "JOB_QUEUE_WAIT_SECONDS", wait_metric)

    worker._mark_job_running(_job(run_after_delta=60.0))

    assert wait_metric.label_calls == []
    assert wait_metric.observations == []


@pytest.mark.asyncio
async def test_claim_job_by_id_handles_missing_lock_and_missing_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return no job if the lock query or subsequent model lookup yields nothing."""
    monkeypatch.setattr(settings, "observability_metrics_enabled", False)
    identifier = uuid.uuid4()
    missing_lock = _Session(scalar_values=[None])
    assert await worker._claim_job_by_id(missing_lock, identifier) is None  # type: ignore[arg-type]
    assert missing_lock.execute_parameters == [{"job_queue_uuid": identifier}]

    missing_model = _Session(scalar_values=[identifier])
    assert await worker._claim_job_by_id(missing_model, identifier) is None  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_claim_job_by_id_marks_existing_job_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mark a due locked queue record running when its model row still exists."""
    monkeypatch.setattr(settings, "observability_metrics_enabled", False)
    job = _job()
    session = _Session(
        scalar_values=[job.job_queue_uuid],
        models={job.job_queue_uuid: job},
    )

    claimed = await worker._claim_job_by_id(session, job.job_queue_uuid)  # type: ignore[arg-type]

    assert claimed is job
    assert job.status == "running"
    assert job.attempt_count == 1


@pytest.mark.asyncio
async def test_claim_one_job_prefers_valid_valkey_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the signaled queue identifier before the PostgreSQL fallback scan."""
    job = _job()
    calls: list[object] = []
    monkeypatch.setattr(worker, "valkey_queue_enabled", lambda: True)

    async def pop_signal() -> object:
        return job.job_queue_uuid

    async def claim(_session: object, identifier: object) -> object:
        calls.append(identifier)
        return job

    monkeypatch.setattr(worker, "pop_due_job_signal", pop_signal)
    monkeypatch.setattr(worker, "_claim_job_by_id", claim)
    session = _Session()

    assert await worker.claim_one_job(session) is job  # type: ignore[arg-type]
    assert calls == [job.job_queue_uuid]
    assert session.execute_parameters == []


@pytest.mark.asyncio
async def test_claim_one_job_falls_back_after_stale_valkey_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fall back to the authoritative PostgreSQL queue if a signal cannot be claimed."""
    job = _job()
    monkeypatch.setattr(settings, "observability_metrics_enabled", False)
    monkeypatch.setattr(worker, "valkey_queue_enabled", lambda: True)

    async def pop_signal() -> object:
        return uuid.uuid4()

    async def stale_claim(_session: object, _identifier: object) -> None:
        return None

    monkeypatch.setattr(worker, "pop_due_job_signal", pop_signal)
    monkeypatch.setattr(worker, "_claim_job_by_id", stale_claim)
    session = _Session(
        scalar_values=[job.job_queue_uuid],
        models={job.job_queue_uuid: job},
    )

    assert await worker.claim_one_job(session) is job  # type: ignore[arg-type]
    assert session.execute_parameters == [None]


@pytest.mark.asyncio
async def test_claim_one_job_handles_empty_and_disappeared_fallback_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return no job for an empty fallback queue or a concurrently removed model row."""
    monkeypatch.setattr(worker, "valkey_queue_enabled", lambda: False)
    empty = _Session(scalar_values=[None])
    assert await worker.claim_one_job(empty) is None  # type: ignore[arg-type]

    identifier = uuid.uuid4()
    disappeared = _Session(scalar_values=[identifier])
    assert await worker.claim_one_job(disappeared) is None  # type: ignore[arg-type]


def test_publish_job_metrics_respects_disable_and_optional_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Publish outcome counters always and processing duration only when supplied."""
    counter = _Metric()
    duration = _Metric()
    monkeypatch.setattr(worker, "JOB_QUEUE_JOBS_TOTAL", counter)
    monkeypatch.setattr(worker, "JOB_QUEUE_PROCESSING_SECONDS", duration)

    monkeypatch.setattr(settings, "observability_metrics_enabled", False)
    worker._publish_job_metrics(job_type="snapshot", outcome="succeeded", duration_s=1.2)
    assert counter.increment_calls == 0

    monkeypatch.setattr(settings, "observability_metrics_enabled", True)
    worker._publish_job_metrics(job_type="snapshot", outcome="succeeded", duration_s=None)
    assert counter.label_calls == [{"job_type": "snapshot", "outcome": "succeeded"}]
    assert counter.increment_calls == 1
    assert duration.observations == []

    worker._publish_job_metrics(job_type="snapshot", outcome="failed", duration_s=2.5)
    assert counter.increment_calls == 2
    assert duration.label_calls == [{"job_type": "snapshot", "outcome": "failed"}]
    assert duration.observations == [2.5]


@pytest.mark.asyncio
async def test_worker_sleeps_when_queue_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Back off once when no job is available without spinning forever in the test."""
    session = _Session()

    async def no_job(_session: object) -> None:
        return None

    async def stop_sleep(delay: float) -> None:
        assert delay == 0.25
        raise _StopWorker

    monkeypatch.setattr(worker, "claim_one_job", no_job)
    monkeypatch.setattr(worker.asyncio, "sleep", stop_sleep)

    with pytest.raises(_StopWorker):
        await worker.run_worker_forever(lambda: session, {}, poll_interval_s=0.25)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_worker_marks_unknown_handler_failed_then_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail a job with an unknown type inside a transaction, then continue polling."""
    session = _Session()
    job = _job(job_type="unknown")
    calls = 0

    async def claim(_session: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            return job
        raise _StopWorker

    monkeypatch.setattr(worker, "claim_one_job", claim)

    with pytest.raises(_StopWorker):
        await worker.run_worker_forever(lambda: session, {})  # type: ignore[arg-type]

    assert job.status == "failed"
    assert job.last_error == "Unknown job_type: unknown"
    assert job.finished_at is not None
    assert session.begin_calls >= 2


@pytest.mark.asyncio
async def test_worker_marks_success_and_publishes_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch a known handler, persist success, and publish its duration outcome."""
    session = _Session()
    job = _job()
    claim_calls = 0
    handler_calls: list[tuple[object, object]] = []
    metric_calls: list[tuple[str, str, float | None]] = []

    async def claim(_session: object) -> object:
        nonlocal claim_calls
        claim_calls += 1
        if claim_calls == 1:
            return job
        raise _StopWorker

    async def handler(factory: object, claimed_job: object) -> None:
        handler_calls.append((factory, claimed_job))

    def publish(*, job_type: str, outcome: str, duration_s: float | None) -> None:
        metric_calls.append((job_type, outcome, duration_s))

    factory = lambda: session
    monkeypatch.setattr(worker, "claim_one_job", claim)
    monkeypatch.setattr(worker, "_publish_job_metrics", publish)

    with pytest.raises(_StopWorker):
        await worker.run_worker_forever(factory, {"snapshot": handler})  # type: ignore[arg-type]

    assert handler_calls == [(factory, job)]
    assert job.status == "succeeded"
    assert job.last_error is None
    assert job.finished_at is not None
    assert len(metric_calls) == 1
    assert metric_calls[0][0:2] == ("snapshot", "succeeded")
    assert metric_calls[0][2] is not None


@pytest.mark.asyncio
async def test_worker_marks_handler_exception_failed_and_publishes_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist a bounded failure result when a known job handler raises."""
    session = _Session()
    job = _job()
    claim_calls = 0
    metric_calls: list[tuple[str, str, float | None]] = []

    async def claim(_session: object) -> object:
        nonlocal claim_calls
        claim_calls += 1
        if claim_calls == 1:
            return job
        raise _StopWorker

    async def failing_handler(_factory: object, _job: object) -> None:
        raise RuntimeError("synthetic handler failure")

    def publish(*, job_type: str, outcome: str, duration_s: float | None) -> None:
        metric_calls.append((job_type, outcome, duration_s))

    monkeypatch.setattr(worker, "claim_one_job", claim)
    monkeypatch.setattr(worker, "_publish_job_metrics", publish)

    with pytest.raises(_StopWorker):
        await worker.run_worker_forever(  # type: ignore[arg-type]
            lambda: session,
            {"snapshot": failing_handler},
        )

    assert job.status == "failed"
    assert job.last_error == "synthetic handler failure"
    assert job.finished_at is not None
    assert len(metric_calls) == 1
    assert metric_calls[0][0:2] == ("snapshot", "failed")
    assert metric_calls[0][2] is not None
