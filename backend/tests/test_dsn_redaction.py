from app.dsn_redaction import redact_dsn_error_message

def test_redact_dsn_error_message_with_underscore_scheme():
    dsn = "invalid_scheme://user:supersecretpass@host/db"
    msg = "Error connecting to invalid_scheme://user:supersecretpass@host/db"
    redacted = redact_dsn_error_message(msg, dsn)
    assert "supersecretpass" not in redacted
    assert "user:***@host" in redacted or "***" in redacted

def test_redact_dsn_error_message_normal():
    dsn = "postgres://user:supersecretpass@host/db"
    msg = "Error: password supersecretpass is wrong"
    redacted = redact_dsn_error_message(msg, dsn)
    assert "supersecretpass" not in redacted
    assert "Error: password *** is wrong" in redacted

def test_redact_dsn_error_message_with_query_params():
    dsn = "postgres://user:pass@host/db?password=supersecret&token=abc12345"
    msg = "Failed with password=supersecret and token abc12345"
    redacted = redact_dsn_error_message(msg, dsn)
    assert "supersecret" not in redacted
    assert "abc12345" not in redacted

def test_redact_dsn_error_message_with_query_params_encoded():
    dsn = "postgres://user:pass@host/db?password=super%20secret&token=abc%2B123"
    msg = "Failed with password=super secret and token abc+123"
    redacted = redact_dsn_error_message(msg, dsn)
    assert "super secret" not in redacted
    assert "abc+123" not in redacted

def test_redact_dsn_no_password_but_assignment():
    dsn = "postgres://user@host/db"
    msg = "Some internal error: secret_key = mysecretvalue123"
    redacted = redact_dsn_error_message(msg, dsn)
    assert "mysecretvalue123" not in redacted
    assert "secret_key = ***" in redacted

def test_redact_dsn_no_match():
    dsn = "postgres://user:pass@host/db"
    msg = "Connection timed out"
    redacted = redact_dsn_error_message(msg, dsn)
    assert redacted == "Connection timed out"

def test_redact_dsn_empty_query_param():
    dsn = "postgres://user:pass@host/db?token="
    msg = "Failed to connect"
    redacted = redact_dsn_error_message(msg, dsn)
    assert redacted == msg

def test_redact_dsn_irrelevant_query_param():
    dsn = "postgres://user:pass@host/db?timeout=30"
    msg = "Failed after 30s"
    redacted = redact_dsn_error_message(msg, dsn)
    # The '30' should not be redacted because it's not a secret key
    assert "30" in redacted
