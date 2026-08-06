"""Fail-closed database DSN secret redaction for bounded diagnostics."""

from __future__ import annotations

import re
from urllib.parse import quote, quote_plus, unquote, unquote_plus, urlsplit

_SECRET_KEY_PATTERN = re.compile(
    r"(?:pass(?:word|wd)?|pwd|token|secret|private[_-]?key|api[_-]?key|"
    r"access[_-]?key|auth(?:entication)?)",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<prefix>\b[\w.-]*(?:pass(?:word|wd)?|pwd|token|secret|private[_-]?key|"
    r"api[_-]?key|access[_-]?key|auth(?:entication)?)[\w.-]*\s*[:=]\s*)"
    r"(?P<value>[^&\s,;\"'<>]+)",
    re.IGNORECASE,
)


def _split_dsn_best_effort(dsn: str) -> tuple[str, str]:
    """Return authority and query text when strict URL splitting fails.

    The fallback performs only bounded string slicing. It exists because
    malformed authorities such as an unbalanced IPv6 bracket can make
    :func:`urllib.parse.urlsplit` raise before embedded credentials are
    available for redaction.
    """

    remainder = dsn
    scheme_separator = remainder.find("://")
    if scheme_separator != -1:
        remainder = remainder[scheme_separator + 3 :]
    remainder = remainder.split("#", 1)[0]
    if "?" in remainder:
        remainder, query = remainder.split("?", 1)
    else:
        query = ""
    authority = remainder.split("/", 1)[0]
    return authority, query


def _password_candidates_from_dsn(dsn: str) -> set[str]:
    """Return exact secret spellings that a database driver may expose.

    URL user-information uses :func:`urllib.parse.unquote`, preserving a
    literal plus sign. Query values use form decoding through
    :func:`urllib.parse.unquote_plus`. Raw, decoded, and canonical encoded
    spellings are retained so driver-specific rendering remains covered.
    """

    candidates: set[str] = set()
    password: str | None = None
    try:
        parsed = urlsplit(dsn)
        if "://" in dsn and not parsed.netloc:
            parsed = urlsplit("http://" + dsn.split("://", 1)[1])
        authority = parsed.netloc
        password = parsed.password
        query = parsed.query
    except ValueError:
        authority, query = _split_dsn_best_effort(dsn)

    if password:
        decoded_password = unquote(password)
        candidates.update(
            {password, decoded_password, quote(decoded_password, safe="")}
        )

    if "@" in authority:
        user_information = authority.rsplit("@", 1)[0]
        if ":" in user_information:
            raw_password = user_information.split(":", 1)[1]
            decoded_password = unquote(raw_password)
            candidates.update(
                {
                    raw_password,
                    decoded_password,
                    quote(decoded_password, safe=""),
                }
            )

    for query_part in query.split("&"):
        key, separator, raw_value = query_part.partition("=")
        if not separator:
            continue
        if not _SECRET_KEY_PATTERN.search(unquote_plus(key)):
            continue
        decoded_value = unquote_plus(raw_value)
        candidates.update(
            {
                raw_value,
                decoded_value,
                quote(decoded_value, safe=""),
                quote_plus(decoded_value, safe=""),
            }
        )

    return {candidate for candidate in candidates if candidate}


def _redact_secret_occurrences(message: str, secret: str) -> str:
    """Replace one case-sensitive secret without corrupting larger words."""

    if not secret:
        return message
    if len(secret) > 4:
        return message.replace(secret, "***")
    pattern = re.compile(rf"(?<!\w){re.escape(secret)}(?!\w)")
    return pattern.sub("***", message)


def redact_dsn_error_message(error_message: str, dsn: str) -> str:
    """Return a driver message with DSN-derived credentials removed.

    Candidate replacement runs longest first and is deliberately
    case-sensitive because passwords and tokens are case-sensitive. A final
    assignment-shaped sanitizer removes values whose sensitive key names are
    visible even when malformed DSN syntax prevents candidate extraction.
    """

    redacted = error_message
    for secret in sorted(
        _password_candidates_from_dsn(dsn), key=len, reverse=True
    ):
        redacted = _redact_secret_occurrences(redacted, secret)
    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", redacted)
