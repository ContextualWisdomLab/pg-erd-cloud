"""Integration-style tests for guarded PostgreSQL introspection connections."""

from __future__ import annotations

import socket
import ssl
from typing import Any

import pytest

from app.pg_introspect import introspect
from app.pg_introspect.dsn_guard import DsnTargetError, validate_postgres_dsn_target
from app.settings import settings


def fake_addrinfo(*ips: str) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    """Return deterministic IPv4 socket metadata for DNS-boundary tests."""

    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 5432)) for ip in ips]


class FakeConnection:
    """Provide the minimal asyncpg surface required by introspection tests."""

    async def fetchval(self, *_args: object) -> str:
        """Return a deterministic PostgreSQL server version."""

        return "16.0"

    async def fetch(self, *_args: object) -> list[dict[str, object]]:
        """Return no catalog rows for the bounded connection test."""

        return []

    async def close(self) -> None:
        """Close the fake connection without side effects."""

        return None


@pytest.mark.asyncio
async def test_introspection_connects_to_validated_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use only the validated public IP while retaining the original DSN."""

    captured: dict[str, Any] = {}

    async def fake_connect(dsn: str, **kwargs: object) -> FakeConnection:
        """Record the exact driver inputs and return a fake connection."""

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
    """Bind verified TLS SNI to the allowlisted hostname, not its resolved IP."""

    captured: dict[str, Any] = {}

    async def fake_connect(dsn: str, **kwargs: object) -> FakeConnection:
        """Record the exact TLS connection inputs and return a fake connection."""

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
    assert getattr(captured["ssl"], "_server_hostname") == "db.example.com"


@pytest.mark.parametrize(
    "parameter",
    ["sslrootcert", "sslcert", "sslkey", "sslcrl", "passfile"],
)
@pytest.mark.asyncio
async def test_postgres_dsn_rejects_server_local_file_parameters_before_dns(
    monkeypatch: pytest.MonkeyPatch,
    parameter: str,
) -> None:
    """Reject every asyncpg DSN file parameter before resolving the host."""

    dns_called = False

    async def fake_getaddrinfo(*_args: object, **_kwargs: object) -> object:
        """Fail if the local-file policy is evaluated after DNS."""

        nonlocal dns_called
        dns_called = True
        raise AssertionError("local-file policy must run before DNS")

    monkeypatch.setattr(
        "asyncio.BaseEventLoop.getaddrinfo",
        fake_getaddrinfo,
    )
    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")

    with pytest.raises(
        DsnTargetError,
        match="^database DSN must not reference server-local files$",
    ):
        dsn = (
            "postgresql://db.example.com/app?sslmode=disable&"
            f"{parameter}=%2Frun%2Fsecrets%2Fclient.pem"
        )
        await validate_postgres_dsn_target(dsn)

    assert dns_called is False


@pytest.mark.asyncio
async def test_postgres_dsn_rejects_encoded_local_file_parameter_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decode URI query keys before enforcing the file-parameter denylist."""

    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")

    with pytest.raises(
        DsnTargetError,
        match="^database DSN must not reference server-local files$",
    ):
        await validate_postgres_dsn_target(
            "postgresql://db.example.com/app?ssl%72ootcert=%2Fetc%2Fpasswd"
        )


@pytest.mark.asyncio
async def test_postgres_dsn_local_file_rejection_does_not_reflect_the_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return one fixed error without reflecting a hostile path or log break."""

    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")
    hostile_path = "/run/secrets/client.pem%0Aforged-log-line"

    with pytest.raises(DsnTargetError) as exc_info:
        await validate_postgres_dsn_target(
            f"postgresql://db.example.com/app?SSLROOTCERT={hostile_path}"
        )

    assert str(exc_info.value) == "database DSN must not reference server-local files"
    assert "forged-log-line" not in str(exc_info.value)
