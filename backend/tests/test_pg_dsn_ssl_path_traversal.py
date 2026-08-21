import pytest

from app.pg_introspect.introspect import _connect_guarded_postgres

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "parameter", ["sslrootcert", "sslcert", "sslkey", "sslcrl", "passfile"]
)
@pytest.mark.parametrize("value", ["", "/run/secrets/secret"])
async def test_connect_guarded_postgres_rejects_tls_file_parameters_before_dns(
    monkeypatch: pytest.MonkeyPatch, parameter: str, value: str
) -> None:
    async def fail_if_target_validation_runs(_dsn: str) -> object:
        raise AssertionError("TLS file parameters must be rejected before DNS validation")

    monkeypatch.setattr(
        "app.pg_introspect.introspect.validate_postgres_dsn_target",
        fail_if_target_validation_runs,
    )
    dsn = f"postgresql://u:p@db.example.com/app?{parameter}={value}"

    with pytest.raises(
        ValueError, match="PostgreSQL DSN TLS file parameters are not supported"
    ):
        await _connect_guarded_postgres(dsn, timeout=1)
