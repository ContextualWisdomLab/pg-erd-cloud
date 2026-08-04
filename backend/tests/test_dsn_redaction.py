from app.dsn_redaction import redact_dsn_error_message


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


def test_malformed_dsn_without_query_redacts_password() -> None:
    dsn = "postgresql://user:s3cr3t@[bad/db"
    error = f"driver failed for s3cr3t while using {dsn}"

    redacted = redact_dsn_error_message(error, dsn)

    assert "s3cr3t" not in redacted
    assert "postgresql://user:***@[bad/db" in redacted


def test_custom_scheme_no_slashes() -> None:
    dsn = "snowflake_invalid:user:secretpass@host/db"
    error = f"Connection to {dsn} failed"

    redacted = redact_dsn_error_message(error, dsn)

    assert redacted == "Connection to snowflake_invalid:user:***@host/db failed"


def test_scheme_less_userinfo_password_is_redacted() -> None:
    dsn = "user:secretpass@host/db"
    error = "Connection to user:secretpass@host/db failed after echoing secretpass"

    redacted = redact_dsn_error_message(error, dsn)

    assert redacted == "Connection to user:***@host/db failed after echoing ***"


def test_malformed_scheme_less_authority_uses_best_effort_redaction() -> None:
    dsn = "user:s3cr3t@[bad/db?token=q%2Fsecret"
    error = f"Connection to {dsn} failed after echoing s3cr3t and q/secret"

    redacted = redact_dsn_error_message(error, dsn)

    assert "s3cr3t" not in redacted
    assert "q/secret" not in redacted
    assert "token=***" in redacted


def test_scheme_less_query_secret_with_colon_is_redacted() -> None:
    dsn = "host/db?password=foo:bar"
    error = "Connection to host/db?password=foo:bar failed after echoing foo:bar"

    redacted = redact_dsn_error_message(error, dsn)

    assert redacted == "Connection to host/db?password=*** failed after echoing ***"


def test_scheme_less_userinfo_without_password_or_secret_query_is_unchanged() -> None:
    dsn = "user@host/db?mode=readonly"
    error = f"Connection to {dsn} failed"

    redacted = redact_dsn_error_message(error, dsn)

    assert redacted == error
