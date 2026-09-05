from __future__ import annotations

import socket
import ssl
from typing import Any

import pytest

from app.pg_introspect import introspect
from app.settings import settings


def fake_addrinfo(*ips: str) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 5432)) for ip in ips]


class FakeConnection:
    async def fetchval(self, *_args: object) -> str:
        return "16.0"

    async def fetch(self, *_args: object) -> list[dict[str, object]]:
        return []

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_introspection_enforces_verified_tls_for_default_dsn(
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

    dsn = "postgresql://db.example.com:6543/app"
    await introspect.introspect_postgres(dsn, schema_filter=None)

    assert captured["dsn"] == dsn
    assert captured["host"] == "93.184.216.34"
    assert captured["port"] == 6543
    assert captured["timeout"] == 10
    assert isinstance(captured["ssl"], ssl.SSLContext)
    assert getattr(captured["ssl"], "_server_hostname") == "db.example.com"
    assert captured["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert captured["ssl"].check_hostname is True


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
        "postgresql://db.example.com:6543/app?sslmode=verify-full",
        schema_filter=None,
    )

    assert captured["host"] == "93.184.216.34"
    assert isinstance(captured["ssl"], ssl.SSLContext)
    assert getattr(captured["ssl"], "_server_hostname") == "db.example.com"
    assert captured["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert captured["ssl"].check_hostname is True


@pytest.mark.asyncio
async def test_introspection_dsn_cannot_downgrade_verified_tls(
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
        "postgresql://db.example.com/app?sslmode=disable",
        schema_filter=None,
    )

    assert isinstance(captured["ssl"], ssl.SSLContext)
    assert captured["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert captured["ssl"].check_hostname is True
    assert getattr(captured["ssl"], "_server_hostname") == "db.example.com"
