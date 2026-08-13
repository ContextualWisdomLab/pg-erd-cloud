import pytest
from app.pg_introspect.introspect import _verified_tls_context

def test_verified_tls_context_path_traversal_blocked():
    dsn = "postgresql://user:pass@db.example.com/app?sslmode=verify-full&sslrootcert=/etc/passwd&sslcert=/etc/passwd&sslkey=/etc/passwd"
    with pytest.raises(ValueError, match="TLS certificate path is not in an allowed directory"):
        _verified_tls_context(dsn, "db.example.com")

def test_verified_tls_context_nonexistent_allowed_blocked():
    dsn = "postgresql://user:pass@db.example.com/app?sslmode=verify-full&sslrootcert=/etc/ssl/certs/does_not_exist.pem"
    with pytest.raises(ValueError, match="TLS certificate path does not exist or is not a file"):
        _verified_tls_context(dsn, "db.example.com")
