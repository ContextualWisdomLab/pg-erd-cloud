"""Real Valkey acceptance for identifier-only queue signal separation."""

from __future__ import annotations

import datetime as dt
import os
import uuid
from typing import Any

import pytest

from app.jobs import valkey_queue
from app.settings import settings


@pytest.mark.asyncio
async def test_real_valkey_keeps_migration_and_generic_signals_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dedicated sorted sets contain only their intended UUID identities."""

    url = os.getenv("VALKEY_INTEGRATION_URL")
    if not url:
        pytest.skip("VALKEY_INTEGRATION_URL is not configured")

    suffix = uuid.uuid4().hex
    generic_key = f"pg-erd-cloud:test:job:{suffix}"
    migration_key = f"pg-erd-cloud:test:migration:{suffix}"
    processing_key = f"pg-erd-cloud:test:migration-processing:{suffix}"
    lease_token_key = f"pg-erd-cloud:test:migration-lease:{suffix}"
    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", url)
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    monkeypatch.setattr(settings, "valkey_queue_key", generic_key)
    monkeypatch.setattr(settings, "valkey_migration_run_queue_key", migration_key)
    monkeypatch.setattr(
        settings, "valkey_migration_run_processing_key", processing_key
    )
    monkeypatch.setattr(
        settings, "valkey_migration_run_lease_token_key", lease_token_key
    )

    redis_asyncio: Any = valkey_queue._load_redis_module()
    client: Any = redis_asyncio.from_url(url)
    generic_uuid = uuid.uuid4()
    migration_uuid = uuid.uuid4()
    due_at = dt.datetime(2026, 8, 11, 3, tzinfo=dt.timezone.utc)
    try:
        await client.delete(
            generic_key, migration_key, processing_key, lease_token_key
        )

        assert await valkey_queue.enqueue_job_signal(generic_uuid, due_at) is True
        assert (
            await valkey_queue.enqueue_migration_run_signal(migration_uuid, due_at)
            is True
        )

        assert await client.zrange(generic_key, 0, -1) == [
            str(generic_uuid).encode()
        ]
        assert await client.zrange(migration_key, 0, -1) == [
            str(migration_uuid).encode()
        ]
        assert await valkey_queue.pop_due_job_signal(due_at) == generic_uuid
        assert await client.zrange(generic_key, 0, -1) == []
        assert await client.zrange(migration_key, 0, -1) == [
            str(migration_uuid).encode()
        ]

        claim = await valkey_queue.claim_due_migration_run_signal(
            now=due_at, lease_seconds=30.0
        )
        assert claim is not None
        assert claim.migration_run_uuid == migration_uuid
        assert await client.zrange(migration_key, 0, -1) == []
        assert await client.zrange(processing_key, 0, -1) == [
            str(migration_uuid).encode()
        ]

        stale_claim = valkey_queue.MigrationRunSignalClaim(
            migration_run_uuid=migration_uuid,
            lease_token=uuid.uuid4(),
        )
        renew_at = due_at + dt.timedelta(seconds=10)
        assert await valkey_queue.renew_migration_run_signal(
            claim, now=renew_at, lease_seconds=30.0
        )
        assert not await valkey_queue.renew_migration_run_signal(
            stale_claim, now=renew_at, lease_seconds=30.0
        )
        assert await client.zscore(processing_key, str(migration_uuid)) == (
            renew_at.timestamp() + 30.0
        )
        assert await valkey_queue.ack_migration_run_signal(stale_claim) is False
        assert await client.zrange(processing_key, 0, -1) == [
            str(migration_uuid).encode()
        ]

        retry_at = due_at + dt.timedelta(seconds=1)
        assert await valkey_queue.release_migration_run_signal(claim, retry_at)
        second_claim = await valkey_queue.claim_due_migration_run_signal(
            now=retry_at, lease_seconds=30.0
        )
        assert second_claim is not None
        assert second_claim.migration_run_uuid == migration_uuid
        assert second_claim.lease_token != claim.lease_token
        assert await valkey_queue.ack_migration_run_signal(second_claim)
        assert await client.zrange(processing_key, 0, -1) == []
        assert await client.hlen(lease_token_key) == 0
    finally:
        await client.delete(
            generic_key, migration_key, processing_key, lease_token_key
        )
        await valkey_queue._close_client(client)
