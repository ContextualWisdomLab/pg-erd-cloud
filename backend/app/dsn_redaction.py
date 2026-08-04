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
_DSN_SCHEME_PREFIX_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+._-]*$")
_REDACTION_PARSE_PREFIX = "redaction://"


def _split_dsn_best_effort(dsn: str) -> tuple[str, str]:
    """Extract ``(netloc, query)`` from a DSN without ``urlsplit``.

    ``urllib.parse.urlsplit`` raises ``ValueError`` on malformed authorities,
    such as an unbalanced IPv6 bracket. Redaction must not propagate that
    failure because the original exception can contain credentials. This
    fallback uses bounded string operations to recover the authority and query
    sections without performing network activity.
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
    netloc = remainder.split("/", 1)[0]
    return netloc, query


def _authority_view_without_slashes(dsn: str) -> tuple[str, str | None, str]:
    """Parse the safest authority view for a DSN that omits ``//``.

    ``user:password@host/db`` must retain ``user`` as user information, while
    ``scheme:user:password@host/db`` must remove only its validated scheme
    token. The pre-``@`` colon count disambiguates those two forms. The
    synthetic ``redaction`` scheme is used only by ``urlsplit`` and cannot
    initiate a network request.
    """

    authority_candidate = dsn
    before_at = dsn.rsplit("@", 1)[0]
    scheme_prefix, separator, remainder = dsn.partition(":")
    if (
        separator
        and before_at.count(":") >= 2
        and _DSN_SCHEME_PREFIX_PATTERN.fullmatch(scheme_prefix)
    ):
        authority_candidate = remainder

    normalized = (
        authority_candidate[2:]
        if authority_candidate.startswith("//")
        else authority_candidate
    )
    try:
        parsed = urlsplit(_REDACTION_PARSE_PREFIX + normalized)
    except ValueError:
        netloc, query = _split_dsn_best_effort(normalized)
        return netloc, None, query
    return parsed.netloc, parsed.password, parsed.query


def _password_candidates_from_dsn(dsn: str) -> set[str]:
    """Return encoded and decoded credential candidates extracted from ``dsn``."""

    views: list[tuple[str, str | None, str]] = []
    try:
        parsed = urlsplit(dsn)
    except ValueError:
        netloc, query = _split_dsn_best_effort(dsn)
        views.append((netloc, None, query))
    else:
        views.append((parsed.netloc, parsed.password, parsed.query))
        if not parsed.netloc and "@" in dsn:
            views.append(_authority_view_without_slashes(dsn))

    candidates: set[str] = set()
    for netloc, password, query in views:
        if password:
            decoded_password = unquote(password)
            candidates.add(password)
            candidates.add(decoded_password)
            candidates.add(quote(decoded_password, safe=""))

        if "@" in netloc:
            userinfo = netloc.rsplit("@", 1)[0]
            if ":" in userinfo:
                raw_password = userinfo.split(":", 1)[1]
                decoded_password = unquote(raw_password)
                candidates.add(raw_password)
                candidates.add(decoded_password)
                candidates.add(quote(decoded_password, safe=""))

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
    """Replace ``secret`` while avoiding substring damage for short values."""

    if len(secret) > 4:
        return message.replace(secret, "***")

    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(secret)}(?![A-Za-z0-9])")
    return pattern.sub("***", message)


def redact_dsn_error_message(error_message: str, dsn: str) -> str:
    """Remove DSN-derived credentials from a database-driver error message."""

    redacted = error_message
    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        redacted = _redact_secret_occurrences(redacted, secret)
    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", redacted)
