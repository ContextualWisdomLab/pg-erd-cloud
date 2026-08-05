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


def test_literal_plus_in_userinfo_does_not_create_space_secret() -> None:
    dsn = "postgresql://user:a+b@db.example.com/app"
    error = "driver failed for a+b while unrelated phrase a b remains"

    redacted = redact_dsn_error_message(error, dsn)

    assert "a+b" not in redacted
    assert "unrelated phrase a b remains" in redacted


def test_form_query_plus_still_decodes_to_space() -> None:
    dsn = "postgresql://user:long-secret@db.example.com/app?token=a+b"
    error = "driver exposed token=a+b and decoded value a b"

    redacted = redact_dsn_error_message(error, dsn)

    assert "token=***" in redacted
    assert "decoded value ***" in redacted


def test_short_secret_respects_unicode_word_boundaries() -> None:
    dsn = "postgresql://user:a@db.example.com/app"
    error = "standalone a; embedded 한a글; Latin xay"

    redacted = redact_dsn_error_message(error, dsn)

    assert "standalone ***" in redacted
    assert "한a글" in redacted
    assert "xay" in redacted


def test_short_unicode_secret_respects_unicode_word_boundaries() -> None:
    dsn = "postgresql://user:%EA%B0%80@db.example.com/app"
    error = "standalone 가; embedded 한가글"

    redacted = redact_dsn_error_message(error, dsn)

    assert "standalone ***" in redacted
    assert "한가글" in redacted


def test_short_punctuation_edge_secrets_redact_exact_occurrences() -> None:
    leading_dsn = "postgresql://user:%2Ba@db.example.com/app"
    trailing_dsn = "postgresql://user:a%2B@db.example.com/app"

    leading_redacted = redact_dsn_error_message("values +a and x+a", leading_dsn)
    trailing_redacted = redact_dsn_error_message("values a+ and a+x", trailing_dsn)

    assert "+a" not in leading_redacted
    assert "x***" in leading_redacted
    assert "a+" not in trailing_redacted
    assert "***x" in trailing_redacted
