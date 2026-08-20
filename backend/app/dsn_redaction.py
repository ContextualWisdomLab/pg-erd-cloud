"""Redact DSN-derived credentials from database driver error messages."""

from __future__ import annotations

import re
from urllib.parse import quote, quote_plus, unquote, unquote_plus, urlsplit

_SECRET_KEY_PATTERN = re.compile(
    r"(?:pass(?:word|wd)?|pwd|token|secret|private[_-]?key|api[_-]?key|"
    r"access[_-]?key|auth(?:entication)?)",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<prefix>\b[\w.-]*?(?<![A-Za-z0-9])(?:pass(?:word|wd)?|pwd|token|secret|private[_-]?key|"
    r"api[_-]?key|access[_-]?key|auth(?:entication)?)[\w.-]*?\s*[:=]\s*)"
    r"(?P<value>[^&\s,;\"'<>]+)",
    re.IGNORECASE,
)


def _split_dsn_best_effort(dsn: str) -> tuple[str, str]:
    """Extract the authority and query from a malformed DSN without raising."""

    remainder = dsn
    scheme_sep = remainder.find("://")
    if scheme_sep != -1:
        remainder = remainder[scheme_sep + 3 :]
    remainder = remainder.split("#", 1)[0]
    if "?" in remainder:
        remainder, query = remainder.split("?", 1)
    else:
        query = ""
    netloc = remainder.split("/", 1)[0]
    return netloc, query


def _password_candidates_from_dsn(dsn: str) -> set[str]:
    """Return raw, decoded, and canonical secret representations from a DSN."""

    candidates: set[str] = set()

    password: str | None = None
    try:
        parsed = urlsplit(dsn)
        if "://" in dsn and not parsed.netloc:
            parsed = urlsplit("http://" + dsn.split("://", 1)[1])
        netloc = parsed.netloc
        password = parsed.password
        query = parsed.query
    except ValueError:
        netloc, query = _split_dsn_best_effort(dsn)

    if not password and not netloc and "@" in dsn:
        try:
            parsed_implicit = urlsplit("//" + dsn)
            if parsed_implicit.netloc:
                netloc = parsed_implicit.netloc
                password = parsed_implicit.password
                query = parsed_implicit.query
        except ValueError:
            # Preserve fail-closed best-effort extraction for malformed authorities.
            pass

    if password:
        candidates.add(password)
        decoded = unquote(password)
        candidates.add(decoded)
        candidates.add(quote(decoded, safe=""))

    if "@" in netloc:
        userinfo = netloc.rsplit("@", 1)[0]
        if ":" in userinfo:
            raw_password = userinfo.split(":", 1)[1]
            candidates.add(raw_password)
            decoded_raw = unquote(raw_password)
            candidates.add(decoded_raw)
            candidates.add(quote(decoded_raw, safe=""))

    for part in query.split("&"):
        key, separator, raw_value = part.partition("=")
        if not separator:
            continue
        if not _SECRET_KEY_PATTERN.search(unquote_plus(key)):
            continue
        decoded_value = unquote_plus(raw_value)
        candidates.add(raw_value)
        candidates.add(decoded_value)
        candidates.add(quote(decoded_value, safe=""))
        candidates.add(quote_plus(decoded_value, safe=""))

    return {candidate for candidate in candidates if candidate}


def _redact_secret_occurrences(message: str, secret: str) -> str:
    """Replace exact secret occurrences while protecting larger Unicode words."""

    if not secret:
        return message

    if len(secret) > 4:
        pattern = re.compile(re.escape(secret), re.IGNORECASE)
        return pattern.sub("***", message)

    pattern = re.compile(
        rf"(?<!\w){re.escape(secret)}(?!\w)",
        flags=re.UNICODE | re.IGNORECASE,
    )
    return pattern.sub("***", message)


def redact_dsn_error_message(error_message: str, dsn: str) -> str:
    """Redact DSN-derived secrets from a database driver error message.

    Args:
        error_message: Driver or connection text that may contain credential
            assignments or representations derived from the DSN.
        dsn: The database connection string used to derive raw, decoded, and
            canonical encoded secret candidates.

    Returns:
        The complete error message with detected secrets replaced by ``***``.
        Unrelated text and message length are otherwise preserved.
    """

    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", error_message)
    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        redacted = _redact_secret_occurrences(redacted, secret)
    return redacted
