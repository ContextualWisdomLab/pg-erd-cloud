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
_WORD_CHARACTER_PATTERN = re.compile(r"\w")


def _split_dsn_best_effort(dsn: str) -> tuple[str, str]:
    """Extract ``(authority, query)`` from a malformed DSN without validation.

    ``urllib.parse.urlsplit`` raises ``ValueError`` for malformed authorities,
    including an unbalanced IPv6 bracket. Redaction must not fail and expose the
    original driver message, so this bounded fallback recovers only the two
    credential-bearing regions with plain string slicing.
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
    """Return exact secret spellings that a database driver may disclose.

    User-information and query strings have different decoding rules. A plus
    sign in ``scheme://user:password@host`` is literal, so those values use
    :func:`urllib.parse.unquote`. Query values follow form encoding, where a
    plus sign represents a space, so only that domain uses
    :func:`urllib.parse.unquote_plus`.
    """

    candidates: set[str] = set()

    password: str | None = None
    try:
        parsed = urlsplit(dsn)
        if "://" in dsn and not parsed.netloc:
            # Keep urlsplit's parsing contract while substituting only an
            # unrecognised scheme so user-information remains discoverable.
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

    if "@" in netloc:
        userinfo = netloc.rsplit("@", 1)[0]
        if ":" in userinfo:
            raw_password = userinfo.split(":", 1)[1]
            candidates.add(raw_password)
            decoded_raw = unquote(raw_password)
            candidates.add(decoded_raw)
            candidates.add(quote(decoded_raw, safe=""))

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


def _is_unicode_word_character(character: str) -> bool:
    """Return whether one character matches Python's Unicode-aware ``\w``."""

    return _WORD_CHARACTER_PATTERN.fullmatch(character) is not None


def _redact_secret_occurrences(message: str, secret: str) -> str:
    """Replace one secret without corrupting larger Unicode identifiers.

    Long candidates are unlikely to be ordinary words and are replaced exactly.
    Short candidates use a boundary only when their corresponding edge is a
    Unicode word character. Punctuation-edge secrets therefore remain
    redactable next to text, while an ASCII or non-ASCII word fragment inside a
    larger identifier is preserved.
    """

    if not secret:
        return message

    if len(secret) > 4:
        return message.replace(secret, "***")

    start_boundary = (
        r"(?<!\w)" if _is_unicode_word_character(secret[0]) else ""
    )
    end_boundary = r"(?!\w)" if _is_unicode_word_character(secret[-1]) else ""
    pattern = re.compile(rf"{start_boundary}{re.escape(secret)}{end_boundary}")
    return pattern.sub("***", message)


def redact_dsn_error_message(error_message: str, dsn: str) -> str:
    """Redact DSN-derived credentials from a database-driver error message.

    The function is best effort and deliberately returns a sanitized message
    rather than raising when the DSN is malformed. Candidate replacement runs
    longest first, then a final key-name sanitizer removes assignment-shaped
    secrets that the DSN parser could not recover.
    """

    redacted = error_message
    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        redacted = _redact_secret_occurrences(redacted, secret)
    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\g<prefix>***", redacted)
