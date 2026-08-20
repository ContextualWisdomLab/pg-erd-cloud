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


def test_unrelated_assignment_key_is_preserved() -> None:
    dsn = "postgresql://user@db.example.com/app"
    error = "driver reported bypass=enabled"

    assert redact_dsn_error_message(error, dsn) == error


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


def test_userinfo_literal_plus_is_not_decoded_as_space() -> None:
    dsn = "postgresql://user:a+b@db.example.com/app"
    error = "driver exposed a+b, but the unrelated phrase a b must remain"

    redacted = redact_dsn_error_message(error, dsn)

    assert "a+b" not in redacted
    assert "unrelated phrase a b must remain" in redacted


def test_userinfo_space_encoding_does_not_redact_literal_plus() -> None:
    dsn = "postgresql://user:a%20b@db.example.com/app"
    error = "driver exposed a b and a%20b; unrelated literal a+b must remain"

    redacted = redact_dsn_error_message(error, dsn)

    assert redacted == "driver exposed *** and ***; unrelated literal a+b must remain"


def test_short_unicode_secret_uses_unicode_word_boundaries() -> None:
    dsn = "postgresql://user@db.example.com/app?token=키"
    error = "standalone 키 must be hidden while 비밀키값 remains readable"

    redacted = redact_dsn_error_message(error, dsn)

    assert redacted == "standalone *** must be hidden while 비밀키값 remains readable"


def test_short_punctuation_secret_is_not_redacted_inside_larger_text() -> None:
    dsn = "postgresql://user:+a+@db.example.com/app"
    error = "isolated +a+ must be hidden while x+a+y remains readable"

    redacted = redact_dsn_error_message(error, dsn)

    assert "isolated *** must be hidden" in redacted
    assert "x+a+y remains readable" in redacted


def test_punctuation_secret_is_redacted_when_adjacent_to_equals() -> None:
    dsn = "postgresql://user:+a+@db.example.com/app"
    error = "driver failed with password=+a+"

    redacted = redact_dsn_error_message(error, dsn)

    assert "password=***" in redacted


def test_redact_secret_occurrences_case_insensitive() -> None:
    dsn = "postgresql://user:SECRET@db.example.com/app?token=KeY"
    error = "driver failed with secret and key"

    redacted = redact_dsn_error_message(error, dsn)

    assert redacted == "driver failed with *** and ***"


def test_mixed_dsn_and_assignment_pattern() -> None:
    dsn = "postgresql://user:secret123@localhost/db"
    error1 = "DSN: user:secret123@localhost and password = secret123"
    error2 = "password = secret123 and DSN: user:secret123@localhost"

    assert redact_dsn_error_message(error1, dsn) == (
        "DSN: user:***@localhost and password = ***"
    )
    assert redact_dsn_error_message(error2, dsn) == (
        "password = *** and DSN: user:***@localhost"
    )


def test_schemeless_dsn_password_redaction() -> None:
    dsn = "user:pass123@localhost/db"
    error = "Connection failed for user:pass123@localhost"

    result = redact_dsn_error_message(error, dsn)

    assert result == "Connection failed for user:***@localhost"


def test_long_error_message_is_redacted_without_truncation() -> None:
    dsn = "postgresql://user:secret123@localhost/db"
    error = f"prefix {'x' * 1200} secret123 suffix"

    redacted = redact_dsn_error_message(error, dsn)

    assert redacted.startswith("prefix ")
    assert "x" * 1200 in redacted
    assert redacted.endswith(" *** suffix")
