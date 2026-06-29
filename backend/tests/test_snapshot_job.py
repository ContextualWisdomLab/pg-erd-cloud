from __future__ import annotations

import datetime as dt
import uuid

import pytest

from app.jobs.snapshot_job import handle_snapshot_job
from app.models import DbConnection, JobQueue, SchemaSnapshot, SchemaSnapshotData
from app.security import encrypt_text


class MockSession:
    def __init__(self):
        self.objects = {}
        self.added = []

    def begin(self):
        class ContextManager:
            async def __aenter__(self):
                pass

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return ContextManager()

    async def get(self, model, id):
        return self.objects.get((model, id))

    def add(self, obj):
        self.added.append(obj)


@pytest.mark.asyncio
async def test_handle_snapshot_job_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot_id = uuid.uuid4()
    db_conn_id = uuid.uuid4()

    mock_session = MockSession()

    snapshot = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_id,
        db_connection_uuid=db_conn_id,
        schema_filter="public",
        status="pending",
    )

    encrypted = encrypt_text("postgresql://localhost/db")
    conn = DbConnection(
        db_connection_uuid=db_conn_id,
        dsn_ciphertext=encrypted.ciphertext,
        dsn_nonce=encrypted.nonce,
    )

    mock_session.objects[(SchemaSnapshot, snapshot_id)] = snapshot
    mock_session.objects[(DbConnection, db_conn_id)] = conn

    job = JobQueue(
        job_queue_uuid=uuid.uuid4(),
        payload_json={"schema_snapshot_uuid": str(snapshot_id)},
    )

    def session_factory():
        class ContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return ContextManager()

    async def failing_introspect(dsn, schema_filter):
        raise ValueError("Simulated introspection failure")

    monkeypatch.setattr("app.jobs.snapshot_job.introspect_database", failing_introspect)

    with pytest.raises(ValueError, match="Simulated introspection failure"):
        await handle_snapshot_job(session_factory, job)

    assert snapshot.status == "failed"
    assert snapshot.error_message == "Simulated introspection failure"
    assert isinstance(snapshot.finished_at, dt.datetime)


@pytest.mark.asyncio
async def test_handle_snapshot_job_success(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot_id = uuid.uuid4()
    db_conn_id = uuid.uuid4()

    mock_session = MockSession()

    snapshot = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_id,
        db_connection_uuid=db_conn_id,
        schema_filter="public",
        status="pending",
    )

    encrypted = encrypt_text("postgresql://localhost/db")
    conn = DbConnection(
        db_connection_uuid=db_conn_id,
        dsn_ciphertext=encrypted.ciphertext,
        dsn_nonce=encrypted.nonce,
    )

    mock_session.objects[(SchemaSnapshot, snapshot_id)] = snapshot
    mock_session.objects[(DbConnection, db_conn_id)] = conn

    job = JobQueue(
        job_queue_uuid=uuid.uuid4(),
        payload_json={"schema_snapshot_uuid": str(snapshot_id)},
    )

    def session_factory():
        class ContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return ContextManager()

    fake_data = {"test_data": "value"}

    async def successful_introspect(dsn, schema_filter):
        return fake_data

    monkeypatch.setattr(
        "app.jobs.snapshot_job.introspect_database", successful_introspect
    )

    await handle_snapshot_job(session_factory, job)

    assert snapshot.status == "succeeded"
    assert snapshot.error_message is None
    assert isinstance(snapshot.finished_at, dt.datetime)

    assert len(mock_session.added) == 1
    added_data = mock_session.added[0]
    assert isinstance(added_data, SchemaSnapshotData)
    assert added_data.schema_snapshot_uuid == snapshot_id
    assert added_data.snapshot_json == fake_data
