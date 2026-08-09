from __future__ import annotations

import datetime as dt
import uuid

import pytest

from app.jobs import valkey_queue
from app.settings import settings


def test_valkey_queue_summary_uses_sentinel_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(valkey_queue.settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(valkey_queue.settings, "valkey_url", None)
    monkeypatch.setattr(
        settings,
        "valkey_sentinel_hosts",
        "valkey-a.local:26379, valkey-b.local:26379",
    )
    monkeypatch.setattr(valkey_queue.settings, "valkey_sentinel_master", "mymaster")

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
    monkeypatch.setattr(valkey_queue.settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(valkey_queue.settings, "valkey_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(valkey_queue.settings, "valkey_sentinel_hosts", None)

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
    monkeypatch.setattr(valkey_queue.settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(valkey_queue.settings, "valkey_url", None)
    monkeypatch.setattr(valkey_queue.settings, "valkey_sentinel_hosts", "missing-port")

    with pytest.raises(ValueError, match="host:port"):
        valkey_queue.valkey_queue_config_summary()

def test_valkey_queue_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test when backend is not valkey
    monkeypatch.setattr(valkey_queue.settings, "job_queue_backend", "postgres")
    assert valkey_queue.valkey_queue_enabled() is False

    # Test when backend is valkey, but no url or sentinel hosts
    monkeypatch.setattr(valkey_queue.settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(valkey_queue.settings, "valkey_url", None)
    monkeypatch.setattr(valkey_queue.settings, "valkey_sentinel_hosts", None)
    assert valkey_queue.valkey_queue_enabled() is False

    # Test when backend is valkey, and url is set
    monkeypatch.setattr(valkey_queue.settings, "valkey_url", "redis://localhost:6379")
    assert valkey_queue.valkey_queue_enabled() is True

    # Test when backend is valkey, and sentinel hosts is set
    monkeypatch.setattr(valkey_queue.settings, "valkey_url", None)
    monkeypatch.setattr(valkey_queue.settings, "valkey_sentinel_hosts", "valkey:26379")
    assert valkey_queue.valkey_queue_enabled() is True
