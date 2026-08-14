from __future__ import annotations

import socket
import ssl
from typing import Any

import asyncpg
import pytest

from app.pg_introspect import introspect
from app.settings import settings


def fake_addrinfo(*ips: str) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 5432)) for ip in ips]


class FakeConnection:
    def __init__(self) -> None:
        self.transaction_options: dict[str, object] | None = None
        self.transaction_started = False
        self.transaction_committed = False
        self.transaction_rolled_back = False

    def transaction(self, **kwargs: object) -> "FakeTransaction":
        self.transaction_options = kwargs
        return FakeTransaction(self)

    async def fetchval(self, *_args: object) -> bool | str:
        if _args and "SELECT EXISTS" in str(_args[0]):
            return False
        return "16.0"

    async def fetch(self, *_args: object) -> list[dict[str, object]]:
        return []

    async def close(self) -> None:
        return None


class FakeTransaction:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def start(self) -> None:
        self.connection.transaction_started = True

    async def commit(self) -> None:
        self.connection.transaction_committed = True

    async def rollback(self) -> None:
        self.connection.transaction_rolled_back = True


class OptionalCitusFailureConnection(FakeConnection):
    def __init__(self, failure: type[asyncpg.PostgresError]) -> None:
        super().__init__()
        self.failure = failure

    async def fetchval(self, *_args: object) -> bool | str:
        if _args and "SELECT EXISTS" in str(_args[0]):
            return True
        return "18.2"

    async def fetch(self, *_args: object) -> list[dict[str, object]]:
        if _args and _args[0] == introspect.queries.CITUS_DISTRIBUTED_TABLES_SQL:
            raise self.failure("optional Citus metadata unavailable")
        return []


@pytest.mark.asyncio
async def test_introspection_connects_to_validated_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_connect(dsn: str, **kwargs: object) -> FakeConnection:
        captured["dsn"] = dsn
        captured.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")
    monkeypatch.setattr(introspect.asyncpg, "connect", fake_connect)

    await introspect.introspect_postgres(
        "postgresql://user:pass@db.example.com:6543/app",
        schema_filter=None,
    )

    assert captured["dsn"] == "postgresql://user:pass@db.example.com:6543/app"
    assert captured["host"] == "93.184.216.34"
    assert captured["port"] == 6543
    assert captured["timeout"] == 10
    assert "ssl" not in captured


@pytest.mark.asyncio
async def test_introspection_preserves_sni_for_verified_tls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_connect(dsn: str, **kwargs: object) -> FakeConnection:
        captured["dsn"] = dsn
        captured.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")
    monkeypatch.setattr(introspect.asyncpg, "connect", fake_connect)

    await introspect.introspect_postgres(
        "postgresql://user:pass@db.example.com:6543/app?sslmode=verify-full",
        schema_filter=None,
    )

    assert captured["host"] == "93.184.216.34"
    assert isinstance(captured["ssl"], ssl.SSLContext)
    assert captured["ssl"]._server_hostname == "db.example.com"


@pytest.mark.asyncio
async def test_introspection_uses_one_read_only_repeatable_read_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()

    async def fake_connect(_dsn: str, **_kwargs: object) -> FakeConnection:
        return connection

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")
    monkeypatch.setattr(introspect.asyncpg, "connect", fake_connect)

    snapshot = await introspect.introspect_postgres(
        "postgresql://user:pass@db.example.com/app", schema_filter=None
    )

    assert connection.transaction_options == {
        "isolation": "repeatable_read",
        "readonly": True,
    }
    assert connection.transaction_started is True
    assert connection.transaction_committed is True
    assert connection.transaction_rolled_back is False
    assert snapshot["snapshot_contract_version"] == 1


@pytest.mark.asyncio
async def test_snapshot_capture_reuses_caller_owned_connection() -> None:
    """Capture live-preflight evidence without opening or closing a connection."""

    connection = FakeConnection()

    snapshot = await introspect.capture_postgres_snapshot(
        connection, schema_filter=None
    )

    assert connection.transaction_options is None
    assert connection.transaction_started is False
    assert connection.transaction_committed is False
    assert connection.transaction_rolled_back is False
    assert snapshot["snapshot_contract_version"] == 1


@pytest.mark.parametrize(
    "failure",
    [
        asyncpg.InsufficientPrivilegeError,
        asyncpg.UndefinedColumnError,
        asyncpg.UndefinedFunctionError,
        asyncpg.UndefinedTableError,
    ],
)
@pytest.mark.asyncio
async def test_optional_citus_metadata_failures_do_not_abort_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    failure: type[asyncpg.PostgresError],
) -> None:
    connection = OptionalCitusFailureConnection(failure)

    async def fake_connect(_dsn: str, **_kwargs: object) -> FakeConnection:
        return connection

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")
    monkeypatch.setattr(introspect.asyncpg, "connect", fake_connect)

    snapshot = await introspect.introspect_postgres(
        "postgresql://user:pass@db.example.com/app", schema_filter=None
    )

    assert snapshot["citus_distributed_tables"] == []
    assert connection.transaction_rolled_back is True
    assert connection.transaction_committed is True
