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

    parsed = urlsplit(dsn)
    redacted_dsn = dsn
    if parsed.password:
        # Avoid naive string replacement of short passwords.
        # Target the exact credential section in the full DSN first.
        # Note: parsed.password is URL-decoded by urlsplit, but we need
        # the exact string from the raw DSN to replace it reliably.
        # We can extract it by splitting the netloc.
        if "@" in parsed.netloc:
            userinfo = parsed.netloc.rsplit("@", 1)[0]
            if ":" in userinfo:
                raw_password = userinfo.split(":", 1)[1]
                redacted_dsn = redacted_dsn.replace(f":{raw_password}@", ":***@")

    redacted = redacted.replace(dsn, redacted_dsn)

    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        if len(secret) > 4:
            redacted = redacted.replace(secret, "***")
        else:
            # For short secrets, only replace them if they are adjacent to boundaries
            # to prevent aggressive over-redaction (e.g. replacing every '1' with '***')
            # Use regex to match the secret with word boundaries or punctuation.
            escaped = re.escape(secret)
            # Match the secret only if it's not surrounded by alphanumeric characters
            pattern = re.compile(rf"(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9])")
            redacted = pattern.sub("***", redacted)

    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", redacted)
