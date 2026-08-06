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
            parsed = urlsplit("http://" + dsn.split("://", 1)[1])
        netloc = parsed.netloc
        password = parsed.password
        query = parsed.query
    except ValueError:
        netloc, query = _split_dsn_best_effort(dsn)

    if password:
        candidates.add(password)
        decoded = unquote(password)
        candidates.add(decoded)
        candidates.add(quote(decoded, safe=""))
        candidates.add(quote_plus(decoded, safe=""))

    if "@" in netloc:
        userinfo = netloc.rsplit("@", 1)[0]
        if ":" in userinfo:
            raw_password = userinfo.split(":", 1)[1]
            candidates.add(raw_password)
            decoded_raw = unquote(raw_password)
            candidates.add(decoded_raw)
            candidates.add(quote(decoded_raw, safe=""))
            candidates.add(quote_plus(decoded_raw, safe=""))

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
    if not secret:
        return message

    if len(secret) > 4:
        pattern = re.compile(re.escape(secret), re.IGNORECASE)
        return pattern.sub("***", message)

    start_boundary = r"(?<!\w)"
    end_boundary = r"(?!\w)"

    pattern = re.compile(rf"{start_boundary}{re.escape(secret)}{end_boundary}", flags=re.UNICODE | re.IGNORECASE)
    return pattern.sub("***", message)


def redact_dsn_error_message(error_message: str, dsn: str) -> str:
    redacted = error_message
    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        redacted = _redact_secret_occurrences(redacted, secret)
    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", redacted)
