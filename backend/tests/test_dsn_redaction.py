from app.dsn_redaction import redact_dsn_error_message, _password_candidates_from_dsn


def test_password_candidates_from_dsn():
    dsn = "snowflake_invalid://user:my_secret_pwd@host/db?password=secret_query"
    candidates = _password_candidates_from_dsn(dsn)
    assert "my_secret_pwd" in candidates
    assert "secret_query" in candidates


def test_redact_dsn_error_message_with_underscore_scheme():
    dsn = "snowflake_invalid://user:my_secret_pwd@host/db?password=secret_query"
    error_message = "Connection failed for user with my_secret_pwd and secret_query."
    redacted = redact_dsn_error_message(error_message, dsn)
    assert "my_secret_pwd" not in redacted
    assert "secret_query" not in redacted
    assert "Connection failed for user with *** and ***." in redacted


def test_redact_dsn_error_message_standard():
    dsn = "postgresql://user:my_secret_pwd@host/db?password=secret_query"
    error_message = "Connection failed for user with my_secret_pwd and secret_query."
    redacted = redact_dsn_error_message(error_message, dsn)
    assert "my_secret_pwd" not in redacted
    assert "secret_query" not in redacted
    assert "Connection failed for user with *** and ***." in redacted
