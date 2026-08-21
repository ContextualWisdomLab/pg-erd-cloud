"""Application lifecycle coverage for the identifier-only dispatch relay."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app import main as main_app
from app.settings import settings


def _blocking_task(
    started: asyncio.Event, cancelled: asyncio.Event
) -> Callable[..., Awaitable[None]]:
    async def run(*_args: object, **_kwargs: object) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    return run


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_opted_in_dispatch_relay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit Valkey relay configuration owns a cancellable lifecycle task."""

    worker_started, worker_cancelled = asyncio.Event(), asyncio.Event()
    relay_started, relay_cancelled = asyncio.Event(), asyncio.Event()
    relay_run = AsyncMock(side_effect=_blocking_task(relay_started, relay_cancelled))
    monkeypatch.setattr(settings, "migration_dispatch_relay_enabled", True)
    monkeypatch.setattr(settings, "migration_dispatch_relay_poll_interval_seconds", 0.25)

    with patch.object(main_app, "valkey_queue_enabled", return_value=True), patch.object(
        main_app,
        "run_worker_forever",
        new=_blocking_task(worker_started, worker_cancelled),
    ), patch.object(
        main_app,
        "run_migration_dispatch_relay_forever",
        new=relay_run,
    ), patch.object(
        main_app,
        "get_pooler_detection",
        new=AsyncMock(
            return_value=SimpleNamespace(
                kind=SimpleNamespace(value="none"), detected=False
            )
        ),
    ):
        async with main_app.lifespan(main_app.app):
            await asyncio.wait_for(worker_started.wait(), timeout=1)
            await asyncio.wait_for(relay_started.wait(), timeout=1)

    await asyncio.wait_for(worker_cancelled.wait(), timeout=1)
    await asyncio.wait_for(relay_cancelled.wait(), timeout=1)
    assert relay_run.call_args.kwargs == {"poll_interval_s": 0.25}


@pytest.mark.asyncio
async def test_lifespan_rejects_relay_without_valkey(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An enabled relay cannot silently poll an unavailable signal backend."""

    monkeypatch.setattr(settings, "migration_dispatch_relay_enabled", True)
    with patch.object(main_app, "valkey_queue_enabled", return_value=False):
        with pytest.raises(RuntimeError, match="requires the Valkey queue backend"):
            async with main_app.lifespan(main_app.app):
                pass


@pytest.mark.asyncio
async def test_lifespan_leaves_dispatch_relay_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The new lifecycle is opt-in until a deployment configures Valkey."""

    worker_started, worker_cancelled = asyncio.Event(), asyncio.Event()
    monkeypatch.setattr(settings, "migration_dispatch_relay_enabled", False)
    with patch.object(
        main_app,
        "run_worker_forever",
        new=_blocking_task(worker_started, worker_cancelled),
    ), patch.object(
        main_app,
        "run_migration_dispatch_relay_forever",
        new=AsyncMock(),
        create=True,
    ) as relay, patch.object(
        main_app,
        "get_pooler_detection",
        new=AsyncMock(
            return_value=SimpleNamespace(
                kind=SimpleNamespace(value="none"), detected=False
            )
        ),
    ):
        async with main_app.lifespan(main_app.app):
            await asyncio.wait_for(worker_started.wait(), timeout=1)

    await asyncio.wait_for(worker_cancelled.wait(), timeout=1)
    relay.assert_not_awaited()
