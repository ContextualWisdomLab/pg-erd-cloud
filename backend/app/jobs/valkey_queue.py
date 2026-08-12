from __future__ import annotations

import datetime as dt
import importlib
import logging
import math
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
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

MAX_EXPIRED_SIGNAL_RECLAIMS = 100

_CLAIM_MIGRATION_RUN_SIGNAL_SCRIPT = """
local expired = redis.call(
  'ZRANGEBYSCORE', KEYS[2], '-inf', ARGV[1], 'LIMIT', 0, ARGV[4]
)
for _, id in ipairs(expired) do
  redis.call('ZREM', KEYS[2], id)
  redis.call('HDEL', KEYS[3], id)
  redis.call('ZADD', KEYS[1], ARGV[1], id)
end

local ids = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 1)
if #ids == 0 then
  return nil
end
if redis.call('ZREM', KEYS[1], ids[1]) ~= 1 then
  return nil
end
redis.call('ZADD', KEYS[2], ARGV[2], ids[1])
redis.call('HSET', KEYS[3], ids[1], ARGV[3])
return ids[1]
"""

_ACK_MIGRATION_RUN_SIGNAL_SCRIPT = """
if redis.call('HGET', KEYS[2], ARGV[1]) ~= ARGV[2] then
  return 0
end
local removed = redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('HDEL', KEYS[2], ARGV[1])
return removed
"""

_RENEW_MIGRATION_RUN_SIGNAL_SCRIPT = """
if redis.call('HGET', KEYS[2], ARGV[1]) ~= ARGV[2] then
  return 0
end
local current_expiry = redis.call('ZSCORE', KEYS[1], ARGV[1])
if not current_expiry then
  return 0
end
if tonumber(current_expiry) <= tonumber(ARGV[3]) then
  return 0
end
if tonumber(ARGV[4]) > tonumber(current_expiry) then
  redis.call('ZADD', KEYS[1], ARGV[4], ARGV[1])
end
return 1
"""

_RELEASE_MIGRATION_RUN_SIGNAL_SCRIPT = """
if redis.call('HGET', KEYS[3], ARGV[1]) ~= ARGV[2] then
  return 0
end
if redis.call('ZREM', KEYS[2], ARGV[1]) ~= 1 then
  redis.call('HDEL', KEYS[3], ARGV[1])
  return 0
end
redis.call('HDEL', KEYS[3], ARGV[1])
redis.call('ZADD', KEYS[1], ARGV[3], ARGV[1])
return 1
"""


class ValkeyQueueUnavailable(RuntimeError):
    """Raised when Valkey is selected but the Python client is unavailable."""


@dataclass(frozen=True)
class MigrationRunSignalClaim:
    """One UUID-only signal claim bound to an opaque, exact lease token."""

    migration_run_uuid: uuid.UUID
    lease_token: uuid.UUID


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
        "migration_run_queue_key": settings.valkey_migration_run_queue_key,
        "migration_run_processing_key": (
            settings.valkey_migration_run_processing_key
        ),
        "migration_run_signal_lease_seconds": (
            settings.migration_run_signal_lease_seconds
        ),
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
        return None
    result = close()
    if hasattr(result, "__await__"):
        _ = await result
    return None


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


async def enqueue_migration_run_signal(
    migration_run_uuid: uuid.UUID,
    run_after: dt.datetime | None = None,
) -> bool:
    """Publish only one migration-run UUID on its isolated Valkey key."""

    if not valkey_queue_enabled():
        return False

    _validate_migration_signal_keys()
    due_at = run_after or dt.datetime.now(dt.timezone.utc)
    if due_at.tzinfo is None or due_at.utcoffset() is None:
        raise ValueError("migration run signal time must include a timezone")
    client: Any | None = None
    try:
        client = await _client()
        await client.zadd(
            settings.valkey_migration_run_queue_key,
            {str(migration_run_uuid): due_at.timestamp()},
        )
        return True
    except Exception:  # noqa: BLE001
        _logger.warning("Valkey migration-run enqueue signal failed", exc_info=True)
        return False
    finally:
        if client is not None:
            await _close_client(client)


def _require_aware_migration_signal_time(value: dt.datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("migration run signal time must include a timezone")


def _validate_migration_signal_keys() -> None:
    keys = (
        settings.valkey_queue_key,
        settings.valkey_migration_run_queue_key,
        settings.valkey_migration_run_processing_key,
        settings.valkey_migration_run_lease_token_key,
    )
    if any(not key for key in keys) or len(set(keys)) != len(keys):
        raise ValueError("Valkey queue and migration signal keys must be distinct")


async def claim_due_migration_run_signal(
    *,
    now: dt.datetime | None = None,
    lease_seconds: float | None = None,
) -> MigrationRunSignalClaim | None:
    """Atomically reclaim expired leases and claim one due run UUID.

    The ready sorted-set payload remains only ``migration_run_uuid``. The
    consumer-generated lease token is stored on the isolated processing side
    and must match for acknowledgement or retry release, preventing a stale
    worker from completing a successor lease. This primitive does not load a
    plan, credentials, target metadata, or SQL.
    """

    if not valkey_queue_enabled():
        return None
    _validate_migration_signal_keys()
    current = now or dt.datetime.now(dt.timezone.utc)
    _require_aware_migration_signal_time(current)
    duration = (
        settings.migration_run_signal_lease_seconds
        if lease_seconds is None
        else lease_seconds
    )
    if not math.isfinite(duration) or not 0 < duration <= 3600:
        raise ValueError("migration run signal lease must be between 0 and 3600")
    lease_token = uuid.uuid4()
    client: Any | None = None
    try:
        client = await _client()
        value = await client.eval(
            _CLAIM_MIGRATION_RUN_SIGNAL_SCRIPT,
            3,
            settings.valkey_migration_run_queue_key,
            settings.valkey_migration_run_processing_key,
            settings.valkey_migration_run_lease_token_key,
            current.timestamp(),
            current.timestamp() + duration,
            str(lease_token),
            MAX_EXPIRED_SIGNAL_RECLAIMS,
        )
        if value is None:
            return None
        try:
            text_value = (
                value.decode("utf-8") if isinstance(value, bytes) else str(value)
            )
            run_uuid = uuid.UUID(text_value)
        except (UnicodeDecodeError, ValueError):
            await client.eval(
                _ACK_MIGRATION_RUN_SIGNAL_SCRIPT,
                2,
                settings.valkey_migration_run_processing_key,
                settings.valkey_migration_run_lease_token_key,
                value if isinstance(value, bytes) else str(value),
                str(lease_token),
            )
            _logger.warning("valkey_migration_signal_invalid_uuid")
            return None
        return MigrationRunSignalClaim(run_uuid, lease_token)
    except Exception:  # noqa: BLE001
        _logger.warning("valkey_migration_signal_claim_failed")
        return None
    finally:
        if client is not None:
            await _close_client(client)


async def ack_migration_run_signal(claim: MigrationRunSignalClaim) -> bool:
    """Acknowledge only the currently leased instance of one run signal."""

    if not valkey_queue_enabled():
        return False
    _validate_migration_signal_keys()
    client: Any | None = None
    try:
        client = await _client()
        removed = await client.eval(
            _ACK_MIGRATION_RUN_SIGNAL_SCRIPT,
            2,
            settings.valkey_migration_run_processing_key,
            settings.valkey_migration_run_lease_token_key,
            str(claim.migration_run_uuid),
            str(claim.lease_token),
        )
        return int(removed) == 1
    except Exception:  # noqa: BLE001
        _logger.warning("valkey_migration_signal_ack_failed")
        return False
    finally:
        if client is not None:
            await _close_client(client)


async def renew_migration_run_signal(
    claim: MigrationRunSignalClaim,
    *,
    now: dt.datetime | None = None,
    lease_seconds: float | None = None,
) -> bool:
    """Extend only the exact active lease without shortening its expiry."""

    if not valkey_queue_enabled():
        return False
    _validate_migration_signal_keys()
    current = now or dt.datetime.now(dt.timezone.utc)
    _require_aware_migration_signal_time(current)
    duration = (
        settings.migration_run_signal_lease_seconds
        if lease_seconds is None
        else lease_seconds
    )
    if not math.isfinite(duration) or not 0 < duration <= 3600:
        raise ValueError("migration run signal lease must be between 0 and 3600")
    client: Any | None = None
    try:
        client = await _client()
        renewed = await client.eval(
            _RENEW_MIGRATION_RUN_SIGNAL_SCRIPT,
            2,
            settings.valkey_migration_run_processing_key,
            settings.valkey_migration_run_lease_token_key,
            str(claim.migration_run_uuid),
            str(claim.lease_token),
            current.timestamp(),
            current.timestamp() + duration,
        )
        return int(renewed) == 1
    except Exception:  # noqa: BLE001
        _logger.warning("valkey_migration_signal_renew_failed")
        return False
    finally:
        if client is not None:
            await _close_client(client)


async def release_migration_run_signal(
    claim: MigrationRunSignalClaim,
    retry_at: dt.datetime,
) -> bool:
    """Return only an exact active lease to the UUID-only ready queue."""

    if not valkey_queue_enabled():
        return False
    _validate_migration_signal_keys()
    _require_aware_migration_signal_time(retry_at)
    client: Any | None = None
    try:
        client = await _client()
        released = await client.eval(
            _RELEASE_MIGRATION_RUN_SIGNAL_SCRIPT,
            3,
            settings.valkey_migration_run_queue_key,
            settings.valkey_migration_run_processing_key,
            settings.valkey_migration_run_lease_token_key,
            str(claim.migration_run_uuid),
            str(claim.lease_token),
            retry_at.timestamp(),
        )
        return int(released) == 1
    except Exception:  # noqa: BLE001
        _logger.warning("valkey_migration_signal_release_failed")
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
    try:
        client = await _client()
        try:
            value = await client.eval(
                _POP_DUE_JOB_SCRIPT,
                1,
                settings.valkey_queue_key,
                current.timestamp(),
            )
        finally:
            await _close_client(client)
    except Exception:  # noqa: BLE001
        _logger.warning("Valkey job pop signal failed", exc_info=True)
        return None

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
