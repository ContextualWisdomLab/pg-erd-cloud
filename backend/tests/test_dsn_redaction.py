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


def test_url_encoded_short_passwords_and_boundaries() -> None:
    dsn = "postgresql://user:a%2Bb@db.example.com/app"
    error = "driver failed for a+b (a%2Bb) with =a+ and b+="

    redacted = redact_dsn_error_message(error, dsn)

    assert "a+b" not in redacted
    assert "a%2Bb" not in redacted
    assert "=a+ and b+=" in redacted


def test_literal_plus_in_userinfo_is_not_decoded_as_query_space() -> None:
    dsn = "postgresql://user:a+b@db.example.com/app"
    error = "driver exposed a+b; unrelated phrase a b must remain"

    redacted = redact_dsn_error_message(error, dsn)

    assert "driver exposed ***" in redacted
    assert "a b must remain" in redacted


def test_short_secret_with_punctuation_requires_token_boundaries() -> None:
    dsn = "postgresql://user:a%2B@db.example.com/app"
    error = "driver exposed a+ while expression a+b remained"

    redacted = redact_dsn_error_message(error, dsn)

    assert "driver exposed ***" in redacted
    assert "expression a+b remained" in redacted
