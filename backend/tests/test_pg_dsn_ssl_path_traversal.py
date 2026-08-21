import pytest
from app.pg_introspect.introspect import _connect_guarded_postgres
from app.pg_introspect.dsn_guard import ValidatedDsnTarget

@pytest.fixture
def mock_target(monkeypatch):
    async def mock_validate(dsn):
        return ValidatedDsnTarget("db.example.com", ("127.0.0.1",), 5432)
    monkeypatch.setattr("app.pg_introspect.introspect.validate_postgres_dsn_target", mock_validate)

@pytest.mark.asyncio
async def test_connect_guarded_postgres_validates_ssl_paths(mock_target):
    # Test across multiple sslmodes, including non-verify-full modes
    for sslmode in ["require", "prefer", "allow", "disable", "verify-ca", "verify-full"]:
        dsn = f"postgresql://u:p@db.example.com/app?sslmode={sslmode}&sslrootcert=/etc/passwd&sslcert=/etc/passwd&sslkey=/etc/passwd"
        with pytest.raises(ValueError, match="TLS certificate path is not in an allowed directory"):
            await _connect_guarded_postgres(dsn, timeout=1)

@pytest.mark.asyncio
async def test_connect_guarded_postgres_validates_crl_and_passfile(mock_target):
    # Test that sslcrl and passfile are also validated
    dsn = "postgresql://u:p@db.example.com/app?sslcrl=/etc/passwd"
    with pytest.raises(ValueError, match="TLS certificate path is not in an allowed directory"):
        await _connect_guarded_postgres(dsn, timeout=1)

    dsn = "postgresql://u:p@db.example.com/app?passfile=/etc/passwd"
    with pytest.raises(ValueError, match="TLS certificate path is not in an allowed directory"):
        await _connect_guarded_postgres(dsn, timeout=1)

@pytest.mark.asyncio
async def test_connect_guarded_postgres_nonexistent_allowed_blocked(mock_target):
    # Test that paths inside an allowed directory must exist
    for sslmode in ["require", "prefer", "allow", "disable", "verify-ca", "verify-full"]:
        dsn = f"postgresql://u:p@db.example.com/app?sslmode={sslmode}&sslrootcert=/etc/ssl/certs/does_not_exist.pem"
        with pytest.raises(ValueError, match="TLS certificate path does not exist or is not a file"):
            await _connect_guarded_postgres(dsn, timeout=1)
