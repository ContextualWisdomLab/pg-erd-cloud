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
    """Extract (netloc, query) from a DSN without ``urlsplit``.

    ``urllib.parse.urlsplit`` raises ``ValueError`` (e.g. "Invalid IPv6 URL")
    on malformed authorities such as an unbalanced ``[``. Redaction must never
    crash on hostile input, otherwise the raw, un-redacted error message could
    still reach a client. This fallback recovers the credential-bearing parts
    with plain string slicing so embedded secrets are still stripped.
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


def _password_candidates_from_dsn(dsn: str) -> set[str]:
    candidates: set[str] = set()

    password: str | None = None
    try:
        parsed = urlsplit(dsn)
        if "://" in dsn and not parsed.netloc:
            # ponytail: keep urlsplit; only swap the non-RFC scheme so userinfo parses.
            parsed = urlsplit("http://" + dsn.split("://", 1)[1])
        netloc = parsed.netloc
        password = parsed.password
        query = parsed.query
    except ValueError:
        # Malformed DSN (e.g. invalid IPv6 literal). Fall back to best-effort
        # parsing so any embedded credentials are still redacted.
        netloc, query = _split_dsn_best_effort(dsn)

    if password:
        candidates.add(password)
        candidates.add(quote(password, safe=""))

    if "@" in netloc:
        userinfo = netloc.rsplit("@", 1)[0]
        if ":" in userinfo:
            raw_password = userinfo.split(":", 1)[1]
            candidates.add(raw_password)
            candidates.add(unquote(raw_password))

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
