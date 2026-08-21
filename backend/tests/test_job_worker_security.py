"""Security regressions for durable job failure evidence."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.worker import run_worker_forever, sanitize_job_error_message


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("postgresql://admin:s3cret@db.example/app"),
        ValueError("password=hunter2 token=opaque SQL=DROP TABLE customer_data"),
        OSError("sampled row value: national-id-123"),
    ],
)
def test_worker_persists_fixed_failure_evidence(error: Exception) -> None:
    """Raw exceptions, credentials, SQL, and row data never enter job rows."""

    message = sanitize_job_error_message(error)

    assert message == "job_handler_failed"
    assert str(error) not in message


def _session_factory() -> MagicMock:
    """Return one reusable async session/context double for worker loops."""

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=False)
    session.begin.return_value = transaction
    factory = MagicMock(return_value=session)
    factory.session = session
    return factory


@pytest.mark.asyncio
async def test_worker_failure_path_never_persists_handler_exception() -> None:
    """The real dispatch failure branch stores only its fixed error code."""

    secret = "postgresql://admin:s3cret@db.example/app"
    job = SimpleNamespace(
        job_type="snapshot",
        status="running",
        last_error=None,
        finished_at=None,
    )
    factory = _session_factory()
    handler = AsyncMock(side_effect=RuntimeError(secret))
    with patch(
        "app.jobs.worker.claim_one_job", new=AsyncMock(side_effect=[job, None])
    ), patch(
        "app.jobs.worker.asyncio.sleep",
        new=AsyncMock(side_effect=asyncio.CancelledError),
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_worker_forever(factory, {"snapshot": handler}, poll_interval_s=0)

    assert job.status == "failed"
    assert job.last_error == "job_handler_failed"
    assert secret not in job.last_error
    assert job.finished_at is not None


@pytest.mark.asyncio
async def test_worker_unknown_type_does_not_persist_untrusted_type_value() -> None:
    """An unregistered type cannot inject metadata through durable errors."""

    untrusted_type = "postgresql://admin:s3cret@db.example/app"
    job = SimpleNamespace(
        job_type=untrusted_type,
        status="running",
        last_error=None,
        finished_at=None,
    )
    factory = _session_factory()
    with patch(
        "app.jobs.worker.claim_one_job", new=AsyncMock(side_effect=[job, None])
    ), patch(
        "app.jobs.worker.asyncio.sleep",
        new=AsyncMock(side_effect=asyncio.CancelledError),
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_worker_forever(factory, {}, poll_interval_s=0)

    assert job.status == "failed"
    assert job.last_error == "job_handler_unavailable"
    assert untrusted_type not in job.last_error
    assert job.finished_at is not None
