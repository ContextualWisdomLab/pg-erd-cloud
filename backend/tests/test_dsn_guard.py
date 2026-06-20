from __future__ import annotations

import socket

import pytest

from app.pg_introspect.dsn_guard import DsnTargetError, validate_postgres_dsn_target
from app.settings import settings


def fake_addrinfo(*ips: str) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 5432))
        for ip in ips
    ]


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://user:pass@127.0.0.1:5432/app",
        "postgresql://user:pass@10.0.0.8:5432/app",
        "postgresql://user:pass@169.254.169.254:5432/app",
        "postgresql://user:pass@[::1]:5432/app",
        "postgresql://user:pass@[::ffff:192.168.1.1]:5432/app",
        "postgresql://user:pass@db.example.com/app?host=127.0.0.1",
        "postgresql://user:pass@db.example.com/app?hostaddr=169.254.169.254",
        "postgresql://user:pass@db.example.com/app?host=127.0.0.1&port=5432",
        "postgresql://user:pass@db.example.com:1234/app?host=localhost",
    ],
)
def test_dsn_guard_rejects_restricted_ip_literals(
    monkeypatch: pytest.MonkeyPatch, dsn: str
) -> None:
    # Need to mock resolve if it passes literal check and tries to resolve db.example.com
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    # also we need to allow db.example.com for query tests
    monkeypatch.setattr(
        settings,
        "db_introspection_allowed_hosts",
        "127.0.0.1,10.0.0.8,169.254.169.254,::1,::ffff:192.168.1.1,db.example.com,*.trusted.example.com",
    )
    with pytest.raises(DsnTargetError, match="restricted IP|localhost"):
        validate_postgres_dsn_target(dsn)


def test_dsn_guard_rejects_localhost() -> None:
    with pytest.raises(DsnTargetError, match="localhost"):
        validate_postgres_dsn_target("postgresql://user:pass@localhost:5432/app")


def test_dsn_guard_rejects_missing_host() -> None:
    with pytest.raises(DsnTargetError, match="include a host"):
        validate_postgres_dsn_target("postgresql:///app")


def test_dsn_guard_rejects_disallowed_scheme() -> None:
    with pytest.raises(DsnTargetError, match="postgres"):
        validate_postgres_dsn_target("mysql://user:pass@db.example.com/app")


def test_dsn_guard_rejects_invalid_port() -> None:
    with pytest.raises(DsnTargetError, match="port"):
        validate_postgres_dsn_target("postgresql://user:pass@db.example.com:bad/app")


def test_dsn_guard_rejects_dns_to_restricted_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("10.0.0.9"),
    )

    with pytest.raises(DsnTargetError, match="restricted IP"):
        validate_postgres_dsn_target("postgresql://user:pass@db.example.com/app")


def test_dsn_guard_allows_public_resolved_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )

    validate_postgres_dsn_target("postgresql://user:pass@db.example.com/app")


def test_dsn_guard_enforces_configured_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(
        settings,
        "db_introspection_allowed_hosts",
        "db.example.com,*.trusted.example.com",
    )

    validate_postgres_dsn_target("postgresql://user:pass@db.example.com/app")
    validate_postgres_dsn_target(
        "postgresql://user:pass@app.trusted.example.com/app"
    )

    with pytest.raises(DsnTargetError, match="allowlist"):
        validate_postgres_dsn_target("postgresql://user:pass@other.example.com/app")
