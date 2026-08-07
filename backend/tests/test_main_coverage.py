"""Lifecycle and small endpoint coverage for the FastAPI application root."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app import main


@pytest.mark.asyncio
async def test_lifespan_detects_pooler_and_cancels_background_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Start the queue worker, record pooler evidence, then cancel it on shutdown."""
    worker_started = asyncio.Event()
    worker_cancelled = asyncio.Event()
    worker_arguments: list[tuple[object, object]] = []

    async def fake_worker(session_factory: object, handlers: object) -> None:
        worker_arguments.append((session_factory, handlers))
        worker_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            worker_cancelled.set()
            raise

    async def detected_pooler() -> object:
        return SimpleNamespace(kind=SimpleNamespace(value="pgbouncer"), detected=True)

    monkeypatch.setattr(main, "run_worker_forever", fake_worker)
    monkeypatch.setattr(main, "get_pooler_detection", detected_pooler)

    async with main.lifespan(FastAPI()):
        await worker_started.wait()
        assert worker_arguments
        session_factory, handlers = worker_arguments[0]
        assert session_factory is main.SessionLocal
        assert handlers == {"snapshot": main.handle_snapshot_job}

    assert worker_cancelled.is_set()


@pytest.mark.asyncio
async def test_lifespan_contains_pooler_detection_failure_and_finished_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep startup available if the best-effort pooler probe fails."""
    worker_finished = asyncio.Event()

    async def finished_worker(_session_factory: object, _handlers: object) -> None:
        worker_finished.set()

    async def failed_detection() -> object:
        raise RuntimeError("synthetic detection failure")

    monkeypatch.setattr(main, "run_worker_forever", finished_worker)
    monkeypatch.setattr(main, "get_pooler_detection", failed_detection)

    async with main.lifespan(FastAPI()):
        await worker_finished.wait()


@pytest.mark.asyncio
async def test_healthz_returns_simple_liveness_contract() -> None:
    """Return the stable process-health response."""
    assert await main.healthz() == {"ok": True}


@pytest.mark.asyncio
async def test_csrf_token_uses_application_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue the CSRF token through the configured application secret boundary."""
    observed: list[str] = []

    def generate(secret: str) -> str:
        observed.append(secret)
        return "signed-csrf-token"

    monkeypatch.setattr(main, "generate_csrf_token", generate)

    assert await main.csrf_token() == {"csrf_token": "signed-csrf-token"}
    assert observed == [main.settings.app_secret]
