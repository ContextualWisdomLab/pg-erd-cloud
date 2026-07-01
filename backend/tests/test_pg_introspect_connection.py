from __future__ import annotations

import socket
from typing import Any

import pytest

from app.pg_introspect import introspect
from app.settings import settings


def fake_addrinfo(*ips: str) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 5432))
        for ip in ips
    ]


class FakeConnection:
    async def fetchval(self, *_args: object) -> str:
        return "16.0"

    async def fetch(self, *_args: object) -> list[dict[str, object]]:
        return []

    async def close(self) -> None:
        return None


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
