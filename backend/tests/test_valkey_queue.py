from __future__ import annotations

import datetime as dt
import uuid

import pytest

from app.jobs import valkey_queue
from app.settings import settings


def test_valkey_queue_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable Valkey only when the backend and one connection mode are configured."""
    monkeypatch.setattr(settings, "job_queue_backend", "postgres")
    assert valkey_queue.valkey_queue_enabled() is False

    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", None)
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    assert valkey_queue.valkey_queue_enabled() is False

    monkeypatch.setattr(settings, "valkey_url", "redis://127.0.0.1:6379/0")
    assert valkey_queue.valkey_queue_enabled() is True

    monkeypatch.setattr(settings, "valkey_url", None)
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", "valkey-a.local:26379")
    assert valkey_queue.valkey_queue_enabled() is True


def test_valkey_queue_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report Sentinel, direct URL, and disabled modes deterministically."""
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", "valkey.local:26379")
    monkeypatch.setattr(settings, "valkey_url", None)
    assert valkey_queue.valkey_queue_mode() == "sentinel"

    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    monkeypatch.setattr(settings, "valkey_url", "redis://localhost:6379/0")
    assert valkey_queue.valkey_queue_mode() == "url"

    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    monkeypatch.setattr(settings, "valkey_url", None)
    assert valkey_queue.valkey_queue_mode() == "disabled"


def test_format_sentinel_hosts_supports_empty_multiple_and_iterable_inputs() -> None:
    """Serialize Sentinel host tuples without depending on concrete list input."""
    assert valkey_queue.format_sentinel_hosts([]) == ""
    assert (
        valkey_queue.format_sentinel_hosts(
            [("valkey-a.local", 26379), ("valkey-b.local", 26379)]
        )
        == "valkey-a.local:26379,valkey-b.local:26379"
    )
    hosts = (host for host in [("127.0.0.1", 6379)])
    assert valkey_queue.format_sentinel_hosts(hosts) == "127.0.0.1:6379"


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


def test_valkey_queue_rejects_invalid_sentinel_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", None)
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", "missing-port")

    with pytest.raises(ValueError, match="host:port"):
        valkey_queue.valkey_queue_config_summary()
