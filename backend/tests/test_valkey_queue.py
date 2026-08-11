from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.jobs import valkey_queue
from app.settings import settings


def _enable_url_valkey(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)


def test_valkey_queue_summary_uses_sentinel_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", None)
    monkeypatch.setattr(
        settings,
        "valkey_sentinel_hosts",
        "valkey-a.local:26379, valkey-b.local:26379",
    )
    monkeypatch.setattr(settings, "valkey_sentinel_master", "mymaster")

    summary = valkey_queue.valkey_queue_config_summary()

    assert summary["enabled"] is True
    assert summary["mode"] == "sentinel"
    assert summary["sentinel_master"] == "mymaster"
    assert summary["sentinel_count"] == 2
    assert summary["migration_run_queue_key"] == (
        settings.valkey_migration_run_queue_key
    )
    assert "valkey-a.local:26379" not in str(summary)


@pytest.mark.asyncio
async def test_enqueue_signal_is_best_effort_without_redis_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)

    def missing_module(_name: str) -> object:
        raise ModuleNotFoundError("redis")

    monkeypatch.setattr(valkey_queue.importlib, "import_module", missing_module)

    ok = await valkey_queue.enqueue_job_signal(
        uuid.uuid4(),
        dt.datetime.now(dt.timezone.utc),
    )

    assert ok is False


def test_valkey_modes_and_host_formatting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuration helpers cover disabled, URL, and empty sentinel entries."""

    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    monkeypatch.setattr(settings, "valkey_url", "redis://valkey:6379/0")
    assert valkey_queue.valkey_queue_enabled() is True
    assert valkey_queue.valkey_queue_mode() == "url"

    monkeypatch.setattr(settings, "valkey_url", None)
    assert valkey_queue.valkey_queue_enabled() is False
    assert valkey_queue.valkey_queue_mode() == "disabled"
    assert valkey_queue._parse_sentinel_hosts(None) == []
    assert valkey_queue._parse_sentinel_hosts(" , valkey:26379, ") == [
        ("valkey", 26379)
    ]
    assert valkey_queue.format_sentinel_hosts([("a", 1), ("b", 2)]) == "a:1,b:2"

    monkeypatch.setattr(settings, "job_queue_backend", "database")
    monkeypatch.setattr(settings, "valkey_url", "redis://valkey:6379/0")
    assert valkey_queue.valkey_queue_enabled() is False


@pytest.mark.parametrize("raw", [":26379", "valkey:0", "valkey:65536"])
def test_valkey_queue_rejects_invalid_sentinel_components(raw: str) -> None:
    with pytest.raises(ValueError):
        valkey_queue._parse_sentinel_hosts(raw)


def test_load_redis_module_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = object()
    monkeypatch.setattr(valkey_queue.importlib, "import_module", lambda _name: module)
    assert valkey_queue._load_redis_module() is module

    def missing(_name: str) -> object:
        raise ModuleNotFoundError("redis")

    monkeypatch.setattr(valkey_queue.importlib, "import_module", missing)
    with pytest.raises(valkey_queue.ValkeyQueueUnavailable, match="redis-py"):
        valkey_queue._load_redis_module()


@pytest.mark.asyncio
async def test_client_supports_url_and_sentinel_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis_client = object()
    redis_module = SimpleNamespace(from_url=MagicMock(return_value=redis_client))
    monkeypatch.setattr(valkey_queue, "_load_redis_module", lambda: redis_module)
    _enable_url_valkey(monkeypatch)
    assert await valkey_queue._client() is redis_client
    redis_module.from_url.assert_called_once_with(settings.valkey_url)

    sentinel_client = object()
    sentinel = SimpleNamespace(master_for=MagicMock(return_value=sentinel_client))
    sentinel_class = MagicMock(return_value=sentinel)
    sentinel_module = SimpleNamespace(Sentinel=sentinel_class)
    monkeypatch.setattr(
        valkey_queue.importlib,
        "import_module",
        lambda name: sentinel_module if name == "redis.asyncio.sentinel" else object(),
    )
    monkeypatch.setattr(settings, "valkey_url", None)
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", "sentinel:26379")
    monkeypatch.setattr(settings, "valkey_sentinel_master", "primary")
    assert await valkey_queue._client() is sentinel_client
    sentinel_class.assert_called_once_with([("sentinel", 26379)])
    sentinel.master_for.assert_called_once_with("primary")


@pytest.mark.asyncio
async def test_client_rejects_incomplete_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(valkey_queue, "_load_redis_module", lambda: object())
    monkeypatch.setattr(settings, "valkey_url", None)
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", "sentinel:26379")
    monkeypatch.setattr(settings, "valkey_sentinel_master", None)
    with pytest.raises(ValueError, match="VALKEY_SENTINEL_MASTER"):
        await valkey_queue._client()

    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    with pytest.raises(ValueError, match="VALKEY_URL"):
        await valkey_queue._client()


@pytest.mark.asyncio
async def test_close_client_supports_absent_sync_and_async_close() -> None:
    await valkey_queue._close_client(SimpleNamespace())

    close = MagicMock(return_value=None)
    await valkey_queue._close_client(SimpleNamespace(close=close))
    close.assert_called_once_with()

    aclose = AsyncMock()
    await valkey_queue._close_client(SimpleNamespace(aclose=aclose))
    aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_migration_signal_contains_only_run_uuid_on_separate_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Migration signals cannot collide with generic job-queue identities."""

    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    run_uuid = uuid.uuid4()
    run_after = dt.datetime(2026, 8, 11, 6, tzinfo=dt.timezone.utc)
    client = SimpleNamespace(zadd=AsyncMock(), aclose=AsyncMock())
    monkeypatch.setattr(valkey_queue, "_client", AsyncMock(return_value=client))

    ok = await valkey_queue.enqueue_migration_run_signal(run_uuid, run_after)

    assert ok is True
    client.zadd.assert_awaited_once_with(
        settings.valkey_migration_run_queue_key,
        {str(run_uuid): run_after.timestamp()},
    )
    assert settings.valkey_migration_run_queue_key != settings.valkey_queue_key
    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_migration_signal_is_disabled_without_valkey(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disabled optional queue performs no client I/O."""

    monkeypatch.setattr(settings, "job_queue_backend", "database")
    client_factory = AsyncMock()
    monkeypatch.setattr(valkey_queue, "_client", client_factory)

    assert await valkey_queue.enqueue_migration_run_signal(uuid.uuid4()) is False
    client_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_signal_rejects_naive_schedule_before_client_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue scores require an unambiguous instant."""

    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    client_factory = AsyncMock()
    monkeypatch.setattr(valkey_queue, "_client", client_factory)

    with pytest.raises(ValueError, match="timezone"):
        await valkey_queue.enqueue_migration_run_signal(
            uuid.uuid4(), dt.datetime(2026, 8, 11, 6)
        )

    client_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_signal_failure_is_closed_and_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A queue write failure remains retryable and always releases the client."""

    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    client = SimpleNamespace(
        zadd=AsyncMock(side_effect=ConnectionError("queue unavailable")),
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(valkey_queue, "_client", AsyncMock(return_value=client))

    assert await valkey_queue.enqueue_migration_run_signal(uuid.uuid4()) is False
    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_generic_enqueue_disabled_success_and_client_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_uuid = uuid.uuid4()
    run_after = dt.datetime(2026, 8, 11, 8, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(settings, "job_queue_backend", "database")
    client_factory = AsyncMock()
    monkeypatch.setattr(valkey_queue, "_client", client_factory)
    assert await valkey_queue.enqueue_job_signal(job_uuid, run_after) is False
    client_factory.assert_not_awaited()

    _enable_url_valkey(monkeypatch)
    good_client = SimpleNamespace(zadd=AsyncMock(), aclose=AsyncMock())
    monkeypatch.setattr(
        valkey_queue, "_client", AsyncMock(return_value=good_client)
    )
    assert await valkey_queue.enqueue_job_signal(job_uuid, run_after) is True
    good_client.zadd.assert_awaited_once_with(
        settings.valkey_queue_key, {str(job_uuid): run_after.timestamp()}
    )
    good_client.aclose.assert_awaited_once()

    bad_client = SimpleNamespace(
        zadd=AsyncMock(side_effect=ConnectionError("unavailable")),
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(valkey_queue, "_client", AsyncMock(return_value=bad_client))
    assert await valkey_queue.enqueue_job_signal(job_uuid, run_after) is False
    bad_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_pop_due_signal_disabled_none_bytes_and_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_queue_backend", "database")
    client_factory = AsyncMock()
    monkeypatch.setattr(valkey_queue, "_client", client_factory)
    assert await valkey_queue.pop_due_job_signal() is None
    client_factory.assert_not_awaited()

    _enable_url_valkey(monkeypatch)
    now = dt.datetime(2026, 8, 11, 9, tzinfo=dt.timezone.utc)
    job_uuid = uuid.uuid4()
    for value, expected in ((None, None), (str(job_uuid).encode(), job_uuid), ("bad", None)):
        client = SimpleNamespace(eval=AsyncMock(return_value=value), aclose=AsyncMock())
        monkeypatch.setattr(valkey_queue, "_client", AsyncMock(return_value=client))
        assert await valkey_queue.pop_due_job_signal(now) == expected
        client.eval.assert_awaited_once_with(
            valkey_queue._POP_DUE_JOB_SCRIPT,
            1,
            settings.valkey_queue_key,
            now.timestamp(),
        )
        client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_pop_due_signal_default_clock_and_client_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_url_valkey(monkeypatch)
    success_client = SimpleNamespace(eval=AsyncMock(return_value=None), aclose=AsyncMock())
    monkeypatch.setattr(
        valkey_queue, "_client", AsyncMock(return_value=success_client)
    )
    assert await valkey_queue.pop_due_job_signal() is None
    success_client.aclose.assert_awaited_once()

    failing_client = SimpleNamespace(
        eval=AsyncMock(side_effect=ConnectionError("unavailable")),
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(
        valkey_queue, "_client", AsyncMock(return_value=failing_client)
    )
    assert await valkey_queue.pop_due_job_signal() is None
    failing_client.aclose.assert_awaited_once()

    monkeypatch.setattr(
        valkey_queue,
        "_client",
        AsyncMock(side_effect=valkey_queue.ValkeyQueueUnavailable("missing")),
    )
    assert await valkey_queue.pop_due_job_signal() is None


def test_valkey_queue_rejects_invalid_sentinel_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", None)
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", "missing-port")

    with pytest.raises(ValueError, match="host:port"):
        valkey_queue.valkey_queue_config_summary()
