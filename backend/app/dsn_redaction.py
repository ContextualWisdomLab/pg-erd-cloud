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

    ``urllib.parse.urlsplit`` raises ``ValueError`` (for example, ``Invalid IPv6
    URL``) on malformed authorities such as an unbalanced ``[``. Redaction must
    never crash on hostile input, otherwise the raw error message could still
    reach a client. This fallback recovers credential-bearing sections with
    plain string slicing so embedded secrets can still be removed.
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


def _authority_view_without_slashes(dsn: str) -> tuple[str, str | None, str]:
    """Return the safest authority interpretation for a DSN omitting ``//``.

    A value such as ``user:password@host/db`` is parsed as one complete
    scheme-less authority. A custom no-slash scheme such as
    ``scheme:user:password@host/db`` is parsed only after removing its validated
    leading scheme token. Choosing one format-aware interpretation prevents the
    scheme token from being mistaken for a username while retaining the entire
    query. The placeholder scheme is used solely for local parsing and never
    causes network activity.
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
    """Extract every plausible encoded and decoded secret from a DSN."""

    views: list[tuple[str, str | None, str]] = []
    try:
        parsed = urlsplit(dsn)
    except ValueError:
        # Malformed DSN (for example, an invalid IPv6 literal). Fall back to
        # best-effort parsing so any embedded credentials are still redacted.
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
            key, sep, raw_value = part.partition("=")
            if not sep:
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
    """Replace one secret while avoiding substring damage for short values."""

    if len(secret) > 4:
        return message.replace(secret, "***")

    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(secret)}(?![A-Za-z0-9])")
    return pattern.sub("***", message)


def redact_dsn_error_message(error_message: str, dsn: str) -> str:
    """Redact DSN-derived secrets from a driver error message."""

    redacted = error_message
    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        redacted = _redact_secret_occurrences(redacted, secret)
    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", redacted)
