"""Final branch coverage for queue worker control-flow edges."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.jobs import worker


class _Result:
    """SQLAlchemy-like result with one optional scalar."""

    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        """Return the configured scalar."""
        return self.value


class _Transaction:
    """No-op asynchronous transaction context."""

    async def __aenter__(self) -> "_Transaction":
        """Enter the transaction."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Exit without suppressing errors."""
        return None


class _Session:
    """Minimal async worker session."""

    async def __aenter__(self) -> "_Session":
        """Enter the session."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Exit the session."""
        return None

    def begin(self) -> _Transaction:
        """Return one no-op transaction."""
        return _Transaction()

    async def execute(self, _statement: object) -> _Result:
        """Return an empty fallback queue result."""
        return _Result(None)


class _StopWorker(RuntimeError):
    """Sentinel terminating the infinite production loop after one full iteration."""


@pytest.mark.asyncio
async def test_claim_one_job_falls_back_when_valkey_has_no_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the PostgreSQL queue when Valkey is enabled but has no due identifier."""
    monkeypatch.setattr(worker, "valkey_queue_enabled", lambda: True)

    async def no_signal() -> None:
        return None

    monkeypatch.setattr(worker, "pop_due_job_signal", no_signal)

    assert await worker.claim_one_job(_Session()) is None  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_worker_empty_queue_executes_sleep_continue_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Complete one empty-queue backoff before terminating on the next poll."""
    calls = 0
    slept: list[float] = []

    async def claim(_session: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        raise _StopWorker

    async def sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(worker, "claim_one_job", claim)
    monkeypatch.setattr(worker.asyncio, "sleep", sleep)

    with pytest.raises(_StopWorker):
        await worker.run_worker_forever(
            lambda: _Session(),  # type: ignore[arg-type]
            {"snapshot": lambda *_args: SimpleNamespace()},  # type: ignore[dict-item]
            poll_interval_s=0.125,
        )

    assert calls == 2
    assert slept == [0.125]
