"""Behavioral regressions for fail-closed DSN secret redaction."""

from app.dsn_redaction import (
    _password_candidates_from_dsn,
    _redact_secret_occurrences,
    _split_dsn_best_effort,
    redact_dsn_error_message,
)


def test_redacts_nonstandard_scheme_password_and_query_secret() -> None:
    """Non-RFC schemes retain user-information and query redaction."""

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
    """A short credential is removed without altering larger identifiers."""

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
    """Malformed IPv6 authority text uses the bounded fallback parser."""

    dsn = "postgresql://user:s3cr3t@[bad/db?password=q%2Fsecret"
    error = f"driver failed for s3cr3t with password=q/secret while using {dsn}"
    redacted = redact_dsn_error_message(error, dsn)
    assert "s3cr3t" not in redacted
    assert "q/secret" not in redacted
    assert "password=***" in redacted


def test_literal_plus_in_user_information_is_not_decoded_as_space() -> None:
    """Authority decoding preserves a literal plus and unrelated spaces."""

    dsn = "postgresql://user:a+b@db.example.com/app"
    error = "driver exposed a+b, but the unrelated phrase a b must remain"
    redacted = redact_dsn_error_message(error, dsn)
    assert "a+b" not in redacted
    assert "unrelated phrase a b must remain" in redacted


def test_form_query_plus_decodes_to_space() -> None:
    """Query form encoding covers raw plus and decoded-space renderings."""

    dsn = "postgresql://user:long-secret@db.example.com/app?token=a+b"
    error = "driver exposed token=a+b and decoded value a b"
    redacted = redact_dsn_error_message(error, dsn)
    assert "token=***" in redacted
    assert "decoded value ***" in redacted


def test_short_unicode_secret_uses_unicode_word_boundaries() -> None:
    """Unicode identifiers containing a short secret remain intact."""

    dsn = "postgresql://user@db.example.com/app?token=키"
    error = "token=키 must be hidden while 비밀키값 remains readable"
    redacted = redact_dsn_error_message(error, dsn)
    assert "token=***" in redacted
    assert "비밀키값 remains readable" in redacted


def test_short_punctuation_secret_requires_complete_boundaries() -> None:
    """Punctuation credentials redact standalone occurrences, not substrings."""

    dsn = "postgresql://user:+a+@db.example.com/app"
    error = "isolated +a+ must be hidden while x+a+y remains readable"
    redacted = redact_dsn_error_message(error, dsn)
    assert "isolated *** must be hidden" in redacted
    assert "x+a+y remains readable" in redacted


def test_secret_matching_is_case_sensitive() -> None:
    """Credential case is preserved while assignment values still fail closed."""

    dsn = "postgresql://user:SECRET@db.example.com/app?token=KeY"
    error = "exact SECRET and KeY; unrelated secret and key; token=key"
    redacted = redact_dsn_error_message(error, dsn)
    assert "exact *** and ***" in redacted
    assert "unrelated secret and key" in redacted
    assert "token=***" in redacted


def test_fallback_split_handles_no_scheme_query_or_fragment() -> None:
    """The fallback covers its no-scheme and no-query branches deterministically."""

    assert _split_dsn_best_effort("user:secret@host/path#fragment") == (
        "user:secret@host",
        "",
    )
    assert _split_dsn_best_effort("user:secret@host/path?token=value#fragment") == (
        "user:secret@host",
        "token=value",
    )


def test_candidate_parser_ignores_flags_and_empty_values() -> None:
    """Nonassignments and empty secret values cannot create candidates."""

    candidates = _password_candidates_from_dsn(
        "postgresql://host/app?flag&ordinary=value&token="
    )
    assert candidates == set()


def test_empty_secret_replacement_is_a_noop() -> None:
    """The internal replacement helper is total for an empty candidate."""

    assert _redact_secret_occurrences("stable", "") == "stable"
