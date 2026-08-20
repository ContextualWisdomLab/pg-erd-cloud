from urllib.parse import urlencode

import pytest

from app.pg_introspect import introspect
from app.pg_introspect.dsn_guard import ValidatedDsnTarget


@pytest.fixture
def mock_target(monkeypatch):
    async def mock_validate(dsn):
        return ValidatedDsnTarget("db.example.com", ("127.0.0.1",), 5432)

    monkeypatch.setattr(
        "app.pg_introspect.introspect.validate_postgres_dsn_target", mock_validate
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sslmode", ["require", "prefer", "allow", "disable", "verify-ca", "verify-full"]
)
@pytest.mark.parametrize("parameter", ["sslrootcert", "sslcert", "sslkey"])
async def test_connect_guarded_postgres_validates_ssl_paths(mock_target, sslmode, parameter):
    dsn = _dsn(sslmode=sslmode, **{parameter: "/etc/passwd"})
    with pytest.raises(
        ValueError, match="TLS certificate path is not in an allowed directory"
    ):
        await introspect._connect_guarded_postgres(dsn, timeout=1)


@pytest.mark.asyncio
async def test_connect_guarded_postgres_validates_crl_and_passfile(mock_target):
    for parameter in ("sslcrl", "passfile"):
        dsn = _dsn(**{parameter: "/etc/passwd"})
        with pytest.raises(
            ValueError, match="TLS certificate path is not in an allowed directory"
        ):
            await introspect._connect_guarded_postgres(dsn, timeout=1)


@pytest.mark.asyncio
async def test_connect_guarded_postgres_nonexistent_allowed_blocked(mock_target):
    allowed = introspect.Path("/etc/ssl/certs/does_not_exist.pem")
    with pytest.raises(
        ValueError, match="TLS certificate path does not exist or is not a file"
    ):
        introspect._validate_tls_file_path(str(allowed))


def _dsn(**query: str) -> str:
    """Build a password-free DSN for path-validation tests."""
    return f"postgresql://db.example.com/app?{urlencode(query)}"


def test_tls_path_validation_rejects_normalized_traversal_and_symlink_escape(
    tmp_path, monkeypatch
):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.pem"
    outside.write_text("not a certificate")
    escaped = allowed / "escaped.pem"
    escaped.symlink_to(outside)
    monkeypatch.setattr(introspect, "_TLS_ALLOWED_BASES", (allowed.resolve(),))

    for path in (allowed / "missing.pem", escaped, allowed / ".." / "outside.pem"):
        expected = (
            "TLS certificate path does not exist or is not a file"
            if path == allowed / "missing.pem"
            else "TLS certificate path is not in an allowed directory"
        )
        with pytest.raises(ValueError, match=expected):
            introspect._validate_tls_file_path(str(path))


def test_verified_tls_context_loads_root_and_client_certificate_paths(monkeypatch):
    calls: list[tuple[str, tuple[str, ...]]] = []

    class FakeContext:
        def __init__(self, server_hostname: str) -> None:
            assert server_hostname == "db.example.com"

        def load_verify_locations(self, *, cafile: str) -> None:
            calls.append(("root", (cafile,)))

        def load_cert_chain(self, certfile: str, keyfile: str) -> None:
            calls.append(("client", (certfile, keyfile)))

    monkeypatch.setattr(introspect, "_ServerHostnameSSLContext", FakeContext)
    monkeypatch.setattr(
        introspect,
        "_validate_tls_file_path",
        lambda path: f"validated:{path}",
    )

    introspect._verified_tls_context(
        _dsn(sslrootcert="root.pem", sslcert="client.pem", sslkey="client.key"),
        "db.example.com",
    )

    assert calls == [
        ("root", ("validated:root.pem",)),
        ("client", ("validated:client.pem", "validated:client.key")),
    ]
