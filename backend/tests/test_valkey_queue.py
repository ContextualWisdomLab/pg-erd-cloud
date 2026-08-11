from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import replace
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
    assert summary["migration_run_processing_key"] == (
        settings.valkey_migration_run_processing_key
    )
    assert summary["migration_run_signal_lease_seconds"] == (
        settings.migration_run_signal_lease_seconds
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
    monkeypatch.setattr(valkey_queue, "_load_redis_module", object)
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
async def test_migration_signal_claim_uses_exact_bounded_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A due UUID moves to processing under one opaque lease token."""

    _enable_url_valkey(monkeypatch)
    run_uuid = uuid.uuid4()
    now = dt.datetime(2026, 8, 11, 6, tzinfo=dt.timezone.utc)
    client = SimpleNamespace(
        eval=AsyncMock(return_value=str(run_uuid).encode()),
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(valkey_queue, "_client", AsyncMock(return_value=client))
    monkeypatch.setattr(valkey_queue.uuid, "uuid4", lambda: uuid.UUID(int=7))

    claim = await valkey_queue.claim_due_migration_run_signal(
        now=now, lease_seconds=15.0
    )

    assert claim == valkey_queue.MigrationRunSignalClaim(
        migration_run_uuid=run_uuid,
        lease_token=uuid.UUID(int=7),
    )
    client.eval.assert_awaited_once_with(
        valkey_queue._CLAIM_MIGRATION_RUN_SIGNAL_SCRIPT,
        3,
        settings.valkey_migration_run_queue_key,
        settings.valkey_migration_run_processing_key,
        settings.valkey_migration_run_lease_token_key,
        now.timestamp(),
        now.timestamp() + 15.0,
        str(uuid.UUID(int=7)),
        valkey_queue.MAX_EXPIRED_SIGNAL_RECLAIMS,
    )
    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_migration_signal_ack_and_release_require_exact_lease_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale worker cannot acknowledge or reschedule a successor lease."""

    _enable_url_valkey(monkeypatch)
    claim = valkey_queue.MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4())
    retry_at = dt.datetime(2026, 8, 11, 6, 1, tzinfo=dt.timezone.utc)
    client = SimpleNamespace(
        eval=AsyncMock(side_effect=[0, 1, 1]),
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(valkey_queue, "_client", AsyncMock(return_value=client))

    stale = replace(claim, lease_token=uuid.uuid4())
    assert await valkey_queue.ack_migration_run_signal(stale) is False
    assert await valkey_queue.release_migration_run_signal(claim, retry_at) is True
    assert await valkey_queue.ack_migration_run_signal(claim) is True

    assert client.eval.await_args_list[0].args == (
        valkey_queue._ACK_MIGRATION_RUN_SIGNAL_SCRIPT,
        2,
        settings.valkey_migration_run_processing_key,
        settings.valkey_migration_run_lease_token_key,
        str(claim.migration_run_uuid),
        str(stale.lease_token),
    )
    assert client.eval.await_args_list[1].args == (
        valkey_queue._RELEASE_MIGRATION_RUN_SIGNAL_SCRIPT,
        3,
        settings.valkey_migration_run_queue_key,
        settings.valkey_migration_run_processing_key,
        settings.valkey_migration_run_lease_token_key,
        str(claim.migration_run_uuid),
        str(claim.lease_token),
        retry_at.timestamp(),
    )
    assert client.aclose.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("lease_seconds", [0.0, -1.0, float("inf"), 3600.1])
async def test_migration_signal_claim_rejects_invalid_lease_before_io(
    monkeypatch: pytest.MonkeyPatch,
    lease_seconds: float,
) -> None:
    """Lease configuration cannot create a busy loop or unbounded claim."""

    _enable_url_valkey(monkeypatch)
    client_factory = AsyncMock()
    monkeypatch.setattr(valkey_queue, "_client", client_factory)

    with pytest.raises(ValueError, match="lease must be between"):
        await valkey_queue.claim_due_migration_run_signal(
            lease_seconds=lease_seconds
        )

    client_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_signal_rejects_colliding_keys_before_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready, processing, lease-token, and generic keys must be isolated."""

    _enable_url_valkey(monkeypatch)
    monkeypatch.setattr(
        settings,
        "valkey_migration_run_processing_key",
        settings.valkey_migration_run_queue_key,
    )
    client_factory = AsyncMock()
    monkeypatch.setattr(valkey_queue, "_client", client_factory)

    with pytest.raises(ValueError, match="must be distinct"):
        await valkey_queue.enqueue_migration_run_signal(uuid.uuid4())
    with pytest.raises(ValueError, match="must be distinct"):
        await valkey_queue.claim_due_migration_run_signal()

    client_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_signal_release_rejects_naive_retry_before_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry scheduling requires an unambiguous instant."""

    _enable_url_valkey(monkeypatch)
    client_factory = AsyncMock()
    monkeypatch.setattr(valkey_queue, "_client", client_factory)

    with pytest.raises(ValueError, match="timezone"):
        await valkey_queue.release_migration_run_signal(
            valkey_queue.MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4()),
            dt.datetime(2026, 8, 11, 6),
        )

    client_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_signal_lease_operations_are_disabled_without_valkey(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The optional lease adapter performs no I/O when it is disabled."""

    monkeypatch.setattr(settings, "job_queue_backend", "database")
    client_factory = AsyncMock()
    monkeypatch.setattr(valkey_queue, "_client", client_factory)
    claim = valkey_queue.MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4())

    assert await valkey_queue.claim_due_migration_run_signal() is None
    assert await valkey_queue.ack_migration_run_signal(claim) is False
    assert (
        await valkey_queue.release_migration_run_signal(
            claim, dt.datetime.now(dt.timezone.utc)
        )
        is False
    )
    client_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_signal_claim_handles_empty_text_and_invalid_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty queues are idle; hostile non-UUID members are quarantined."""

    _enable_url_valkey(monkeypatch)
    now = dt.datetime(2026, 8, 11, 6, tzinfo=dt.timezone.utc)
    empty_client = SimpleNamespace(
        eval=AsyncMock(return_value=None), aclose=AsyncMock()
    )
    text_uuid = uuid.uuid4()
    text_client = SimpleNamespace(
        eval=AsyncMock(return_value=str(text_uuid)), aclose=AsyncMock()
    )
    invalid_client = SimpleNamespace(
        eval=AsyncMock(side_effect=[b"not-a-run-uuid", 1]), aclose=AsyncMock()
    )
    client_factory = AsyncMock(
        side_effect=[empty_client, text_client, invalid_client]
    )
    monkeypatch.setattr(valkey_queue, "_client", client_factory)

    assert await valkey_queue.claim_due_migration_run_signal(now=now) is None
    text_claim = await valkey_queue.claim_due_migration_run_signal(now=now)
    assert text_claim is not None
    assert text_claim.migration_run_uuid == text_uuid
    assert await valkey_queue.claim_due_migration_run_signal(now=now) is None

    invalid_ack_args = invalid_client.eval.await_args_list[1].args
    assert invalid_ack_args[:5] == (
        valkey_queue._ACK_MIGRATION_RUN_SIGNAL_SCRIPT,
        2,
        settings.valkey_migration_run_processing_key,
        settings.valkey_migration_run_lease_token_key,
        "not-a-run-uuid",
    )
    assert isinstance(uuid.UUID(invalid_ack_args[5]), uuid.UUID)
    assert all(
        client.aclose.await_count == 1
        for client in (empty_client, text_client, invalid_client)
    )


@pytest.mark.asyncio
async def test_migration_signal_lease_failures_use_fixed_non_secret_logs(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Adapter failures close clients without reflecting exception contents."""

    _enable_url_valkey(monkeypatch)
    marker = "forbidden-queue-log-marker-8a31"
    clients = [
        SimpleNamespace(
            eval=AsyncMock(side_effect=RuntimeError(marker)), aclose=AsyncMock()
        )
        for _ in range(3)
    ]
    monkeypatch.setattr(
        valkey_queue, "_client", AsyncMock(side_effect=clients)
    )
    claim = valkey_queue.MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4())

    assert await valkey_queue.claim_due_migration_run_signal() is None
    assert await valkey_queue.ack_migration_run_signal(claim) is False
    assert (
        await valkey_queue.release_migration_run_signal(
            claim, dt.datetime.now(dt.timezone.utc)
        )
        is False
    )

    assert "valkey_migration_signal_claim_failed" in caplog.text
    assert "valkey_migration_signal_ack_failed" in caplog.text
    assert "valkey_migration_signal_release_failed" in caplog.text
    assert marker not in caplog.text
    assert all(client.aclose.await_count == 1 for client in clients)


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
