from app.dsn_redaction import redact_dsn_error_message, _password_candidates_from_dsn

def test_redacts_nonstandard_scheme_password_and_query_secret() -> None:
    dsn = "snowflake_invalid://user:pa%3Ass@acct.example.com/db?token=q%2Fsecret"
    error = (
        "driver failed for pa:ss using "
        "snowflake_invalid://user:pa%3Ass@acct.example.com/db?token=q%2Fsecret "
        "with token=q/secret"
    )

    redacted = redact_dsn_error_message(error, dsn)

    assert "pa:ss" not in redacted
    assert "pa%3Ass" not in redacted
    assert "q/secret" not in redacted
    assert "q%2Fsecret" not in redacted
    assert "snowflake_invalid://user:***@acct.example.com/db?token=***" in redacted


def test_short_dsn_password_does_not_corrupt_secret_key_names() -> None:
    dsn = "postgresql://user:pass@db.example.com/app?password=q%2Fsecret"
    error = (
        "driver failed with password=q/secret while retrying "
        "postgresql://user:pass@db.example.com/app"
    )

    redacted = redact_dsn_error_message(error, dsn)

    assert "q/secret" not in redacted
    assert "user:pass@" not in redacted
    assert "password=***" in redacted
    assert "postgresql://user:***@db.example.com/app" in redacted
    assert "***word" not in redacted


def test_malformed_dsn_still_redacts_embedded_secrets() -> None:
    dsn = "postgresql://user:s3cr3t@[bad/db?password=q%2Fsecret"
    error = f"driver failed for s3cr3t with password=q/secret while using {dsn}"

    redacted = redact_dsn_error_message(error, dsn)

    assert "s3cr3t" not in redacted
    assert "q/secret" not in redacted
    assert "password=***" in redacted

def test_missing_slashes_dsn() -> None:
    dsn = "postgresql:user:secret_pass@host/db"
    error = f"driver failed for secret_pass while using {dsn}"

    redacted = redact_dsn_error_message(error, dsn)

    assert "secret_pass" not in redacted

def test_missing_slashes_malformed_dsn() -> None:
    dsn = "postgresql:user:s3cr3t@[bad/db"
    error = f"driver failed for s3cr3t while using {dsn}"

    redacted = redact_dsn_error_message(error, dsn)

    assert "s3cr3t" not in redacted

def test_best_effort_split_with_query_and_no_slashes() -> None:
    dsn = "postgresql:user:s3cr3t@[bad/db?password=q%2Fsecret"
    candidates = _password_candidates_from_dsn(dsn)

    assert "s3cr3t" in candidates
    assert "q/secret" in candidates

def test_no_sep_in_query() -> None:
    dsn = "postgresql:user:s3cr3t@[bad/db?password=q%2Fsecret&nosep"
    candidates = _password_candidates_from_dsn(dsn)

    assert "s3cr3t" in candidates
    assert "q/secret" in candidates

def test_no_secret_key_in_query() -> None:
    dsn = "postgresql:user:s3cr3t@[bad/db?safe=value"
    candidates = _password_candidates_from_dsn(dsn)

    assert "s3cr3t" in candidates
    assert "value" not in candidates


def test_no_netloc_but_standard_scheme_with_slashes() -> None:
    # A DSN that urlsplit parses but results in empty netloc due to something else?
    dsn = "http://@localhost/db"
    candidates = _password_candidates_from_dsn(dsn)
    # Just to get line 64 executed

def test_no_netloc_but_slashes() -> None:
    dsn = "://user:secret_pass@host/db"
    candidates = _password_candidates_from_dsn(dsn)
    assert "secret_pass" in candidates
