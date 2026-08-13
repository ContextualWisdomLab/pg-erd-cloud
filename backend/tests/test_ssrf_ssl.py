"""Regression coverage for guarded PostgreSQL TLS file parameters."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qsl, urlencode, urlparse

import pytest

from app.pg_introspect import introspect


@pytest.fixture
def password_free_dsn() -> str:
    """Return a credential-free PostgreSQL DSN for TLS boundary tests."""

    return "postgresql://db.example.com/app"


@pytest.mark.parametrize(
    "parameter", ("sslrootcert", "sslcert", "sslkey")
)
def test_tls_file_parameter_rejects_traversal(
    password_free_dsn: str,
    parameter: str,
) -> None:
    """Reject traversal independently for every file-bearing TLS option."""

    query = urlencode(
        {
            "sslmode": "verify-full",
            parameter: "/etc/ssl/certs/../../../etc/passwd",
        }
    )
    with pytest.raises(
        ValueError,
        match="TLS certificate path is not in an allowed directory",
    ):
        introspect._verified_tls_context(
            f"{password_free_dsn}?{query}",
            "db.example.com",
        )


@pytest.mark.parametrize(
    "parameter", ("sslrootcert", "sslcert", "sslkey")
)
def test_tls_file_parameter_rejects_missing_file(
    password_free_dsn: str,
    parameter: str,
) -> None:
    """Reject missing files independently inside an allowed directory."""

    query = urlencode(
        {
            "sslmode": "verify-full",
            parameter: "/etc/ssl/certs/pg-erd-cloud-missing.pem",
        }
    )
    with pytest.raises(
        ValueError,
        match="TLS certificate path does not exist or is not a file",
    ):
        introspect._verified_tls_context(
            f"{password_free_dsn}?{query}",
            "db.example.com",
        )


def test_tls_file_parameter_rejects_symlink_escape(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    password_free_dsn: str,
) -> None:
    """Reject a symlink inside an allowed root when its target escapes."""

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.pem"
    outside.write_text("not a certificate", encoding="utf-8")
    link = allowed / "root.pem"
    link.symlink_to(outside)
    monkeypatch.setattr(
        introspect,
        "_TLS_FILE_ALLOWED_BASES",
        (allowed.resolve(),),
    )

    query = urlencode(
        {"sslmode": "verify-full", "sslrootcert": str(link)}
    )
    with pytest.raises(
        ValueError,
        match="TLS certificate path is not in an allowed directory",
    ):
        introspect._verified_tls_context(
            f"{password_free_dsn}?{query}",
            "db.example.com",
        )


def test_tls_file_parameters_are_canonicalized_before_connect(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    password_free_dsn: str,
) -> None:
    """Replace all admitted TLS file values with resolved safe paths."""

    allowed = tmp_path / "allowed"
    nested = allowed / "nested"
    nested.mkdir(parents=True)
    root = allowed / "root.pem"
    cert = allowed / "client.pem"
    key = allowed / "client.key"
    for path in (root, cert, key):
        path.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        introspect,
        "_TLS_FILE_ALLOWED_BASES",
        (allowed.resolve(),),
    )

    query = urlencode(
        {
            "sslmode": "require",
            "sslrootcert": str(nested / ".." / root.name),
            "sslcert": str(cert),
            "sslkey": str(key),
        }
    )
    guarded = introspect._guard_tls_file_paths(
        f"{password_free_dsn}?{query}"
    )
    values = dict(
        parse_qsl(urlparse(guarded).query, keep_blank_values=True)
    )
    assert values["sslrootcert"] == str(root.resolve())
    assert values["sslcert"] == str(cert.resolve())
    assert values["sslkey"] == str(key.resolve())


def test_verified_context_loads_canonical_client_chain(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    password_free_dsn: str,
) -> None:
    """Load the verified CA and client chain only from canonical paths."""

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    root = allowed / "root.pem"
    cert = allowed / "client.pem"
    key = allowed / "client.key"
    for path in (root, cert, key):
        path.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        introspect,
        "_TLS_FILE_ALLOWED_BASES",
        (allowed.resolve(),),
    )
    context = MagicMock()
    monkeypatch.setattr(
        introspect,
        "_ServerHostnameSSLContext",
        lambda _hostname: context,
    )

    query = urlencode(
        {
            "sslmode": "verify-full",
            "sslrootcert": str(root),
            "sslcert": str(cert),
            "sslkey": str(key),
        }
    )
    actual = introspect._verified_tls_context(
        f"{password_free_dsn}?{query}",
        "db.example.com",
    )
    assert actual is context
    context.load_verify_locations.assert_called_once_with(
        cafile=str(root.resolve())
    )
    context.load_default_certs.assert_not_called()
    context.load_cert_chain.assert_called_once_with(
        str(cert.resolve()),
        str(key.resolve()),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sslmode",
    ("allow", "prefer", "require", "verify-ca", "verify-full"),
)
async def test_every_tls_mode_guards_paths_before_asyncpg(
    monkeypatch: pytest.MonkeyPatch,
    password_free_dsn: str,
    sslmode: str,
) -> None:
    """Block unsafe paths before asyncpg can parse them in any TLS mode."""

    validate_target = AsyncMock(
        return_value=SimpleNamespace(
            hosts=("93.184.216.34",),
            hostname="db.example.com",
            port=5432,
        )
    )
    connect = AsyncMock()
    monkeypatch.setattr(
        introspect, "validate_postgres_dsn_target", validate_target
    )
    monkeypatch.setattr(introspect.asyncpg, "connect", connect)
    query = urlencode(
        {"sslmode": sslmode, "sslrootcert": "/etc/passwd"}
    )

    with pytest.raises(
        ValueError,
        match="TLS certificate path is not in an allowed directory",
    ):
        await introspect._connect_guarded_postgres(
            f"{password_free_dsn}?{query}",
            timeout=1,
        )
    validate_target.assert_awaited_once()
    connect.assert_not_awaited()
