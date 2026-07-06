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


def _password_candidates_from_dsn(dsn: str) -> set[str]:
    candidates: set[str] = set()

    # Workaround for Python's urllib.parse not parsing schemes with underscores.
    # If the scheme has an underscore, replace it with a hyphen before parsing
    # so that urlsplit() correctly identifies the netloc and credentials.
    colon_idx = dsn.find(":")
    if colon_idx > 0 and "_" in dsn[:colon_idx]:
        prefix = dsn[:colon_idx]
        if all(c.isalnum() or c in "+-." or c == "_" for c in prefix):
            parsed_dsn = prefix.replace("_", "-") + dsn[colon_idx:]
        else:
            parsed_dsn = dsn
    else:
        parsed_dsn = dsn

    parsed = urlsplit(parsed_dsn)

    if parsed.password:
        candidates.add(parsed.password)
        candidates.add(quote(parsed.password, safe=""))

    if "@" in parsed.netloc:
        userinfo = parsed.netloc.rsplit("@", 1)[0]
        if ":" in userinfo:
            raw_password = userinfo.split(":", 1)[1]
            candidates.add(raw_password)
            candidates.add(unquote(raw_password))

    for part in parsed.query.split("&"):
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


def redact_dsn_error_message(error_message: str, dsn: str) -> str:
    """Redact DSN-derived secrets from a driver error message."""

    redacted = error_message
    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        redacted = redacted.replace(secret, "***")
    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", redacted)
