import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.jobs.snapshot_job import _redact_snapshot_error_message
from app.jobs.snapshot_job import handle_snapshot_job
from app.models import DbConnection, JobQueue, SchemaSnapshot
from app.security import encrypt_text


class _FakeTransaction:
    async def __aenter__(self) -> "_FakeTransaction":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class _FakeSession:
    def __init__(self, snapshot: SchemaSnapshot, conn: DbConnection) -> None:
        self.snapshot = snapshot
        self.conn = conn
        self.get = AsyncMock(side_effect=self._get)

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def _get(self, model: object, identity: object) -> object | None:
        if model is SchemaSnapshot:
            return self.snapshot
        if model is DbConnection:
            return self.conn
        return None


def test_redacts_decoded_and_percent_encoded_dsn_passwords() -> None:
    dsn = "postgresql://user:pa%3Ass@db.example.com/app"
    error = "connection failed for pa:ss and original postgresql://user:pa%3Ass@db.example.com/app"

    redacted = _redact_snapshot_error_message(error, dsn)

    assert "pa:ss" not in redacted
    assert "pa%3Ass" not in redacted
    assert redacted.count("***") >= 2


def test_redacts_password_query_parameter_values() -> None:
    dsn = "postgresql://user@db.example.com/app?password=q%2Fsecret&sslmode=require"
    error = "driver failed with password=q/secret from password=q%2Fsecret"

    redacted = _redact_snapshot_error_message(error, dsn)

    assert "q/secret" not in redacted
    assert "q%2Fsecret" not in redacted
    assert "password=***" in redacted


def test_redacts_custom_secret_query_parameter_values() -> None:
    dsn = "postgresql://user@db.example.com/app?tenant_secret=tenant%2Fsecret&sslmode=require"
    error = "driver failed with tenant_secret=tenant/secret from tenant_secret=tenant%2Fsecret"

    redacted = _redact_snapshot_error_message(error, dsn)

    assert "tenant/secret" not in redacted
    assert "tenant%2Fsecret" not in redacted
    assert "tenant_secret=***" in redacted


def test_redacts_secret_assignments_without_dsn_candidates() -> None:
    dsn = "postgresql://user@db.example.com/app"
    error = "driver failed with api_key=abc123 and private-key: top-secret"

    redacted = _redact_snapshot_error_message(error, dsn)

    assert "abc123" not in redacted
    assert "top-secret" not in redacted
    assert "api_key=***" in redacted
    assert "private-key: ***" in redacted


def test_redacts_passwords_from_nonstandard_dsn_scheme() -> None:
    dsn = "snowflake_invalid://user:pa%3Ass@acct.example.com/db?token=q%2Fsecret"
    error = "driver failed for pa:ss with token=q/secret"

    redacted = _redact_snapshot_error_message(error, dsn)

    assert "pa:ss" not in redacted
    assert "q/secret" not in redacted
    assert "token=***" in redacted


@pytest.mark.asyncio
async def test_handle_snapshot_job_persists_and_raises_redacted_error() -> None:
    snapshot_id = uuid.uuid4()
    conn_id = uuid.uuid4()
    dsn = "postgresql://user:pa%3Ass@db.example.com/app"
    encrypted = encrypt_text(dsn)
    snapshot = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_id,
        db_connection_uuid=conn_id,
        schema_filter=None,
    )
    conn = DbConnection(
        db_connection_uuid=conn_id,
        dsn_ciphertext=encrypted.ciphertext,
        dsn_nonce=encrypted.nonce,
    )
    session = _FakeSession(snapshot, conn)
    job = JobQueue(payload_json={"schema_snapshot_uuid": str(snapshot_id)})

    async def fail_introspection(dsn_value: str, schema_filter: str | None) -> dict:
        raise RuntimeError(
            f"connection failed for pa:ss using {dsn_value} and api_key=abc123"
        )

    with patch(
        "app.jobs.snapshot_job.introspect_database",
        side_effect=fail_introspection,
    ):
        with pytest.raises(RuntimeError) as exc_info:
            await handle_snapshot_job(lambda: session, job)

    raised_error = str(exc_info.value)
    assert snapshot.status == "failed"
    assert snapshot.error_message == raised_error
    assert "pa:ss" not in raised_error
    assert "pa%3Ass" not in raised_error
    assert "abc123" not in raised_error
    assert "api_key=***" in raised_error
