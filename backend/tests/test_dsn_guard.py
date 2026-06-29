from __future__ import annotations

import socket

import pytest

from app.pg_introspect.dsn_guard import (
    DsnTargetError,
    _unique_hosts,
    validate_postgres_dsn_target,
)
from app.settings import settings


def fake_addrinfo(*ips: str) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 5432))
        for ip in ips
    ]


def test_unique_hosts_returns_empty_tuple_for_empty_list() -> None:
    assert _unique_hosts([]) == ()


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
        "postgresql://user:pass@db.example.com/app?host=db.example.com,127.0.0.1",
        "postgresql://user:pass@db.example.com/app?hostaddr=93.184.216.34,169.254.169.254",
    ],
)
@pytest.mark.asyncio
async def test_dsn_guard_rejects_restricted_ip_literals(
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
        "127.0.0.1,10.0.0.8,169.254.169.254,::1,::ffff:192.168.1.1,93.184.216.34,db.example.com,*.trusted.example.com",
    )
    with pytest.raises(DsnTargetError, match="restricted IP|localhost"):
        await validate_postgres_dsn_target(dsn)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://user:pass@db.example.com/app?host=",
        "postgresql://user:pass@db.example.com/app?hostaddr=",
        "postgresql://user:pass@db.example.com/app?hostaddr=db.example.com",
        "postgresql://user:pass@db.example.com/app?port=",
        "postgresql://user:pass@db.example.com/app?port=5432,",
        "postgresql://user:pass@db.example.com/app?port=70000",
    ],
)
@pytest.mark.asyncio
async def test_dsn_guard_rejects_invalid_query_overrides(
    monkeypatch: pytest.MonkeyPatch, dsn: str
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(
        settings,
        "db_introspection_allowed_hosts",
        "db.example.com,93.184.216.34",
    )

    with pytest.raises(DsnTargetError, match="query"):
        await validate_postgres_dsn_target(dsn)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://user:pass@[::ffff:10.0.0.8]:5432/app",
        "postgresql://user:pass@[::ffff:127.0.0.1]:5432/app",
        "postgresql://user:pass@[::ffff:169.254.169.254]:5432/app",
        "postgresql://user:pass@db.example.com/app?hostaddr=::ffff:10.0.0.8",
    ],
)
@pytest.mark.asyncio
async def test_dsn_guard_rejects_ipv4_mapped_restricted_addresses(
    monkeypatch: pytest.MonkeyPatch, dsn: str
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(
        settings,
        "db_introspection_allowed_hosts",
        "::ffff:10.0.0.8,::ffff:127.0.0.1,::ffff:169.254.169.254,db.example.com",
    )

    with pytest.raises(DsnTargetError, match="restricted IP"):
        await validate_postgres_dsn_target(dsn)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://user:pass@[::ffff:93.184.216.34]:5432/app",
        "postgresql://user:pass@db.example.com/app?hostaddr=::ffff:93.184.216.34",
    ],
)
@pytest.mark.asyncio
async def test_dsn_guard_allows_public_ipv4_mapped_addresses(
    monkeypatch: pytest.MonkeyPatch, dsn: str
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(
        settings,
        "db_introspection_allowed_hosts",
        "::ffff:93.184.216.34,db.example.com",
    )

    target = await validate_postgres_dsn_target(dsn)
    assert target.hosts == ("93.184.216.34",)


@pytest.mark.asyncio
async def test_dsn_guard_rejects_localhost() -> None:
    with pytest.raises(DsnTargetError, match="localhost"):
        await validate_postgres_dsn_target("postgresql://user:pass@localhost:5432/app")


@pytest.mark.asyncio
async def test_dsn_guard_rejects_missing_host() -> None:
    with pytest.raises(DsnTargetError, match="include a host"):
        await validate_postgres_dsn_target("postgresql:///app")


@pytest.mark.asyncio
async def test_dsn_guard_rejects_disallowed_scheme() -> None:
    with pytest.raises(DsnTargetError, match="postgres"):
        await validate_postgres_dsn_target("mysql://user:pass@db.example.com/app")


@pytest.mark.asyncio
async def test_dsn_guard_rejects_invalid_port() -> None:
    with pytest.raises(DsnTargetError, match="port"):
        await validate_postgres_dsn_target("postgresql://user:pass@db.example.com:bad/app")


@pytest.mark.asyncio
async def test_dsn_guard_rejects_dns_to_restricted_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("10.0.0.9"),
    )
    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")

    with pytest.raises(DsnTargetError, match="restricted IP"):
        await validate_postgres_dsn_target("postgresql://user:pass@db.example.com/app")


@pytest.mark.asyncio
async def test_dsn_guard_allows_public_resolved_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")

    target = await validate_postgres_dsn_target(
        "postgresql://user:pass@db.example.com/app"
    )
    assert target.hosts == ("93.184.216.34",)
    assert target.port is None


@pytest.mark.asyncio
async def test_dsn_guard_returns_validated_connection_ip_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: fake_addrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "db.example.com")

    target = await validate_postgres_dsn_target(
        "postgresql://user:pass@db.example.com:6543/app"
    )

    assert target.hosts == ("93.184.216.34",)
    assert target.port == 6543


@pytest.mark.asyncio
async def test_dsn_guard_rejects_unconfigured_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "db_introspection_allowed_hosts", "")

    with pytest.raises(DsnTargetError, match="allowlist is not configured"):
        await validate_postgres_dsn_target("postgresql://user:pass@db.example.com/app")


@pytest.mark.asyncio
async def test_dsn_guard_enforces_configured_allowlist(
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

    await validate_postgres_dsn_target("postgresql://user:pass@db.example.com/app")
    await validate_postgres_dsn_target(
        "postgresql://user:pass@app.trusted.example.com/app"
    )

    with pytest.raises(DsnTargetError, match="allowlist"):
        await validate_postgres_dsn_target("postgresql://user:pass@other.example.com/app")

@pytest.mark.asyncio
async def test_dsn_guard_rejects_unresolvable_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_gaierror(*args, **kwargs):
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        raise_gaierror,
    )
    monkeypatch.setattr(
        settings,
        "db_introspection_allowed_hosts",
        "db.example.com",
    )

    with pytest.raises(DsnTargetError, match="database host could not be resolved"):
        await validate_postgres_dsn_target("postgresql://user:pass@db.example.com/app")

def test_host_matches_allowed_entry() -> None:
    from app.pg_introspect.dsn_guard import _host_matches_allowed_entry

    assert _host_matches_allowed_entry("db.example.com", "*.example.com") is True
    assert _host_matches_allowed_entry("example.com", "*.example.com") is False
    assert _host_matches_allowed_entry("evil.example.com", "*.example.com") is True

    # SSRF bypasses
    assert _host_matches_allowed_entry("evil.com.example.com", "*.example.com") is True
    assert _host_matches_allowed_entry("evil.com\\.example.com", "*.example.com") is False
    assert _host_matches_allowed_entry("evilexample.com", "*.example.com") is False
