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
    parsed = urlsplit(dsn)

    def add_variations(pw: str) -> None:
        if not pw:
            return

        decoded = unquote_plus(pw)
        candidates.add(pw)
        candidates.add(decoded)
        candidates.add(quote(decoded, safe=""))
        candidates.add(quote_plus(decoded, safe=""))

    if parsed.password:
        add_variations(parsed.password)

    if "@" in parsed.netloc:
        userinfo = parsed.netloc.rsplit("@", 1)[0]
        if ":" in userinfo:
            raw_password = userinfo.split(":", 1)[1]
            add_variations(raw_password)

    for part in parsed.query.split("&"):
        key, sep, raw_value = part.partition("=")
        if not sep:
            continue
        if not _SECRET_KEY_PATTERN.search(unquote_plus(key)):
            continue
        add_variations(raw_value)

    return {candidate for candidate in candidates if candidate}


def redact_dsn_error_message(error_message: str, dsn: str) -> str:
    """Redact DSN-derived secrets from a driver error message."""
    redacted = error_message

    # Apply naive replacements for all candidates.
    # While this may cause over-redaction for very short passwords, it is
    # the safest approach to ensure no secrets leak in error messages.
    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        redacted = redacted.replace(secret, "***")

    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", redacted)
