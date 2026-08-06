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
    """Extract ``(netloc, query)`` from a malformed DSN without ``urlsplit``.

    ``urllib.parse.urlsplit`` raises ``ValueError`` for malformed authorities,
    including an unbalanced IPv6 bracket. Redaction must remain fail closed on
    hostile input so the raw driver message is never returned merely because
    the DSN could not be parsed normally.
    """

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


def _add_userinfo_candidates(candidates: set[str], raw_value: str) -> None:
    """Add raw, decoded, and canonical URL-userinfo secret candidates."""

    if not raw_value:
        return
    decoded_value = unquote(raw_value)
    candidates.add(raw_value)
    candidates.add(decoded_value)
    candidates.add(quote(decoded_value, safe=""))


def _add_query_candidates(candidates: set[str], raw_value: str) -> None:
    """Add raw, decoded, and canonical form-query secret candidates."""

    if not raw_value:
        return
    decoded_value = unquote_plus(raw_value)
    candidates.add(raw_value)
    candidates.add(decoded_value)
    candidates.add(quote(decoded_value, safe=""))
    candidates.add(quote_plus(decoded_value, safe=""))


def _password_candidates_from_dsn(dsn: str) -> set[str]:
    """Return credential representations that a database driver may expose."""

    candidates: set[str] = set()

    password: str | None = None
    try:
        parsed = urlsplit(dsn)
        if "://" in dsn and not parsed.netloc:
            # Keep ``urlsplit`` semantics while substituting only a parseable
            # scheme so non-RFC database schemes still expose their userinfo.
            parsed = urlsplit("http://" + dsn.split("://", 1)[1])
        netloc = parsed.netloc
        password = parsed.password
        query = parsed.query
    except ValueError:
        netloc, query = _split_dsn_best_effort(dsn)

    if password:
        _add_userinfo_candidates(candidates, password)

    if "@" in netloc:
        userinfo = netloc.rsplit("@", 1)[0]
        if ":" in userinfo:
            _add_userinfo_candidates(candidates, userinfo.split(":", 1)[1])

    for part in query.split("&"):
        key, sep, raw_value = part.partition("=")
        if not sep:
            continue
        if not _SECRET_KEY_PATTERN.search(unquote_plus(key)):
            continue
        _add_query_candidates(candidates, raw_value)

    return {candidate for candidate in candidates if candidate}


def _redact_secret_occurrences(message: str, secret: str) -> str:
    """Redact one secret without replacing it inside a larger Unicode word."""

    if not secret:
        return message

    if len(secret) > 4:
        return message.replace(secret, "***")

    # Short secrets are especially prone to corrupting unrelated identifiers.
    # Unicode-aware ``\w`` boundaries protect both alphanumeric secrets and
    # punctuation-bearing values such as ``+a+`` from substring over-redaction.
    pattern = re.compile(rf"(?<!\w){re.escape(secret)}(?!\w)")
    return pattern.sub("***", message)


def redact_dsn_error_message(error_message: str, dsn: str) -> str:
    """Redact DSN-derived credentials from a database-driver error message."""

    redacted = error_message
    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        redacted = _redact_secret_occurrences(redacted, secret)
    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", redacted)
