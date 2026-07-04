from app.dsn_redaction import _password_candidates_from_dsn, redact_dsn_error_message

def test_dsn_redaction_underscore_scheme():
    dsn = "my_custom_db://user:mysecretpassword@host/db"
    candidates = _password_candidates_from_dsn(dsn)
    assert "mysecretpassword" in candidates

def test_dsn_redaction_query_params():
    dsn = "snowflake_test://user@host/db?password=mysecretpassword"
    candidates = _password_candidates_from_dsn(dsn)
    assert "mysecretpassword" in candidates

def test_dsn_redaction_message():
    dsn = "my_custom_db://user:mysecretpassword@host/db"
    msg = "Failed to connect to host with password mysecretpassword."
    redacted = redact_dsn_error_message(msg, dsn)
    assert "mysecretpassword" not in redacted
    assert "***" in redacted

def test_dsn_redaction_standard_scheme():
    dsn = "postgresql://user:standardpass@host/db"
    candidates = _password_candidates_from_dsn(dsn)
    assert "standardpass" in candidates

    # Add a query param test to hit line 47: continue if not _SECRET_KEY_PATTERN
    dsn_with_safe_query = "postgresql://user:standardpass@host/db?timeout=30"
    candidates_safe_query = _password_candidates_from_dsn(dsn_with_safe_query)
    assert "standardpass" in candidates_safe_query
    assert "30" not in candidates_safe_query

    msg = "Connection failed for user, password standardpass"
    redacted = redact_dsn_error_message(msg, dsn)
    assert "standardpass" not in redacted
    assert "***" in redacted
