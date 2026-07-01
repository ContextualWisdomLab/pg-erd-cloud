from __future__ import annotations

import datetime as dt
import uuid

import pytest

from app.jobs import valkey_queue
from app.settings import settings


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

def test_load_redis_module_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_module(_name: str) -> object:
        raise ModuleNotFoundError("redis")

    monkeypatch.setattr(valkey_queue.importlib, "import_module", missing_module)

    with pytest.raises(
        valkey_queue.ValkeyQueueUnavailable,
        match="Valkey queue backend requires redis-py with asyncio support",
    ):
        valkey_queue._load_redis_module()
