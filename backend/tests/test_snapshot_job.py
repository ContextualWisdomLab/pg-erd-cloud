from app.jobs.snapshot_job import _redact_snapshot_error_message


def test_redacts_decoded_and_percent_encoded_dsn_passwords() -> None:
    dsn = "postgresql://user:pa%3Ass@db.example.com/app"
    error = "connection failed for pa:ss and original postgresql://user:pa%3Ass@db.example.com/app"

    redacted = _redact_snapshot_error_message(error, dsn)

    assert "pa:ss" not in redacted
    assert "pa%3Ass" not in redacted
    assert redacted.count("***") >= 2


def test_redacts_password_query_parameter_values() -> None:
    dsn = "postgresql://user@db.example.com/app?password=q%2Fsecret&sslmode=require"
    error = "driver failed with password=q/secret from password=q%2Fsecret"

    redacted = _redact_snapshot_error_message(error, dsn)

    assert "q/secret" not in redacted
    assert "q%2Fsecret" not in redacted
    assert "password=***" in redacted


def test_redacts_custom_secret_query_parameter_values() -> None:
    dsn = "postgresql://user@db.example.com/app?tenant_secret=tenant%2Fsecret&sslmode=require"
    error = "driver failed with tenant_secret=tenant/secret from tenant_secret=tenant%2Fsecret"

    redacted = _redact_snapshot_error_message(error, dsn)

    assert "tenant/secret" not in redacted
    assert "tenant%2Fsecret" not in redacted
    assert "tenant_secret=***" in redacted


def test_redacts_secret_assignments_without_dsn_candidates() -> None:
    dsn = "postgresql://user@db.example.com/app"
    error = "driver failed with api_key=abc123 and private-key: top-secret"

    redacted = _redact_snapshot_error_message(error, dsn)

    assert "abc123" not in redacted
    assert "top-secret" not in redacted
    assert "api_key=***" in redacted
    assert "private-key: ***" in redacted
