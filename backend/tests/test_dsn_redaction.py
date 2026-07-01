from app.dsn_redaction import redact_dsn_error_message, _password_candidates_from_dsn


def test_password_candidates_unsupported_scheme():
    dsn = "snowflake_invalid://user:supersecret123@example.com/db"
    candidates = _password_candidates_from_dsn(dsn)
    assert "supersecret123" in candidates


def test_password_candidates_query_params():
    dsn = "snowflake_invalid://user@example.com/db?password=anothersecret456&token=supersecret789"
    candidates = _password_candidates_from_dsn(dsn)
    assert "anothersecret456" in candidates
    assert "supersecret789" in candidates


def test_redact_error_message_unsupported_scheme():
    dsn = "snowflake_invalid://user:supersecret123@example.com/db"
    error = "Driver error: supersecret123 is invalid for host"
    redacted = redact_dsn_error_message(error, dsn)
    assert "supersecret123" not in redacted
    assert "***" in redacted


def test_redact_error_message_standard():
    dsn = "postgresql://user:dbpass123@localhost/db"
    error = "Connection failed. password: dbpass123."
    redacted = redact_dsn_error_message(error, dsn)
    assert "dbpass123" not in redacted
    assert "***" in redacted
