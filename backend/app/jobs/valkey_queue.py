from __future__ import annotations

import datetime as dt
import importlib
import logging
import uuid
from collections.abc import Iterable
from typing import Any

from app.settings import settings

_logger = logging.getLogger(__name__)

_POP_DUE_JOB_SCRIPT = """
local ids = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 1)
if #ids == 0 then
  return nil
end
if redis.call('ZREM', KEYS[1], ids[1]) == 1 then
  return ids[1]
end
return nil
"""


class ValkeyQueueUnavailable(RuntimeError):
    """Raised when Valkey is selected but the Python client is unavailable."""


def _parse_sentinel_hosts(raw: str | None) -> list[tuple[str, int]]:
    """Parse VALKEY_SENTINEL_HOSTS as comma-separated host:port entries."""

    if not raw:
        return []

    hosts: list[tuple[str, int]] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        host, sep, port_text = item.rpartition(":")
        if not sep or not host:
            raise ValueError("VALKEY_SENTINEL_HOSTS entries must be host:port")
        port = int(port_text)
        if port <= 0 or port > 65535:
            raise ValueError("VALKEY_SENTINEL_HOSTS port out of range")
        hosts.append((host, port))
    return hosts


def valkey_queue_enabled() -> bool:
    """Return whether workers should use Valkey as a queue signal path."""

    if settings.job_queue_backend != "valkey":
        return False
    return bool(settings.valkey_url or settings.valkey_sentinel_hosts)


def valkey_queue_mode() -> str:
    """Return the configured Valkey connection mode for diagnostics."""

    if settings.valkey_sentinel_hosts:
        return "sentinel"
    if settings.valkey_url:
        return "url"
    return "disabled"


def valkey_queue_config_summary() -> dict[str, object]:
    """Expose non-secret Valkey queue configuration for reports/tests."""

    sentinel_hosts = _parse_sentinel_hosts(settings.valkey_sentinel_hosts)
    return {
        "enabled": valkey_queue_enabled(),
        "mode": valkey_queue_mode(),
        "queue_key": settings.valkey_queue_key,
        "sentinel_master": settings.valkey_sentinel_master,
        "sentinel_count": len(sentinel_hosts),
        "lock_ttl_seconds": settings.valkey_lock_ttl_seconds,
    }


def _load_redis_module() -> Any:
    try:
        return importlib.import_module("redis.asyncio")
    except ModuleNotFoundError as exc:
        raise ValkeyQueueUnavailable(
            "Valkey queue backend requires redis-py with asyncio support"
        ) from exc


async def _client() -> Any:
    redis_asyncio = _load_redis_module()
    sentinel_hosts = _parse_sentinel_hosts(settings.valkey_sentinel_hosts)
    if sentinel_hosts:
        if not settings.valkey_sentinel_master:
            raise ValueError(
                "VALKEY_SENTINEL_MASTER is required with VALKEY_SENTINEL_HOSTS"
            )
        sentinel_mod = importlib.import_module("redis.asyncio.sentinel")
        sentinel = sentinel_mod.Sentinel(sentinel_hosts)
        return sentinel.master_for(settings.valkey_sentinel_master)
    if not settings.valkey_url:
        raise ValueError("VALKEY_URL is required when job_queue_backend=valkey")
    return redis_asyncio.from_url(settings.valkey_url)


async def _close_client(client: Any) -> None:
    close = getattr(client, "aclose", None) or getattr(client, "close", None)
    if close is None:
        return
    result = close()
    if hasattr(result, "__await__"):
        await result


async def enqueue_job_signal(
    job_queue_uuid: uuid.UUID,
    run_after: dt.datetime,
) -> bool:
    """Best-effort signal that a DB-backed job is due through Valkey."""

    if not valkey_queue_enabled():
        return False

    client: Any | None = None
    try:
        client = await _client()
        await client.zadd(
            settings.valkey_queue_key,
            {str(job_queue_uuid): run_after.timestamp()},
        )
        return True
    except Exception:  # noqa: BLE001
        _logger.warning("Valkey job enqueue signal failed", exc_info=True)
        return False
    finally:
        if client is not None:
            await _close_client(client)


async def pop_due_job_signal(
    now: dt.datetime | None = None,
) -> uuid.UUID | None:
    """Pop one due job ID from Valkey, if the optional backend is configured."""

    if not valkey_queue_enabled():
        return None

    current = now or dt.datetime.now(dt.timezone.utc)
    client: Any | None = None
    try:
        client = await _client()
        value = await client.eval(
            _POP_DUE_JOB_SCRIPT,
            1,
            settings.valkey_queue_key,
            current.timestamp(),
        )
    except Exception:  # noqa: BLE001
        _logger.warning("Valkey job pop signal failed", exc_info=True)
        return None
    finally:
        if client is not None:
            await _close_client(client)

    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        return uuid.UUID(str(value))
    except ValueError:
        _logger.warning("Valkey queue returned an invalid job UUID: %r", value)
        return None


def format_sentinel_hosts(hosts: Iterable[tuple[str, int]]) -> str:
    """Format sentinel hosts without exposing credentials."""

    return ",".join(f"{host}:{port}" for host, port in hosts)
