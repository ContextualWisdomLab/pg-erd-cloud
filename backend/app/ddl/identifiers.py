"""Dialect-owned SQL identifier validation and rendering.

SQL bind parameters cannot represent object identifiers. Every DDL renderer
therefore uses this module to validate canonical identifiers and emit one
PostgreSQL-compatible, double-quoted token. Punctuation is data inside that
token; it is not filtered with a deny-list.
"""

from __future__ import annotations


MAX_IDENTIFIER_BYTES = 63
MAX_SNOWFLAKE_IDENTIFIER_BYTES = 255


class SqlIdentifierError(ValueError):
    """Raised when an identifier cannot round-trip through PostgreSQL."""


def validate_identifier(identifier: str) -> str:
    """Return *identifier* if PostgreSQL can preserve it exactly.

    PostgreSQL stores at most 63 UTF-8 bytes for an identifier. Accepting a
    longer value would let the server silently truncate it and alias another
    object. NUL cannot occur in PostgreSQL identifiers at all.
    """

    if not isinstance(identifier, str):
        raise SqlIdentifierError("SQL identifier must be text")
    if not identifier:
        raise SqlIdentifierError("SQL identifier must not be empty")
    if "\x00" in identifier:
        raise SqlIdentifierError("SQL identifier must not contain NUL")
    if len(identifier.encode("utf-8")) > MAX_IDENTIFIER_BYTES:
        raise SqlIdentifierError("SQL identifier exceeds PostgreSQL's 63-byte limit")
    return identifier


def validate_snowflake_identifier(identifier: str) -> str:
    """Return *identifier* if Snowflake can preserve it exactly.

    Snowflake accepts identifiers up to 255 UTF-8 bytes. NUL remains invalid
    because it cannot be represented safely in a SQL statement.
    """

    if not isinstance(identifier, str):
        raise SqlIdentifierError("Snowflake identifier must be text")
    if not identifier:
        raise SqlIdentifierError("Snowflake identifier must not be empty")
    if "\x00" in identifier:
        raise SqlIdentifierError("Snowflake identifier must not contain NUL")
    if len(identifier.encode("utf-8")) > MAX_SNOWFLAKE_IDENTIFIER_BYTES:
        raise SqlIdentifierError("Snowflake identifier exceeds the 255-byte limit")
    return identifier


def quote_identifier(identifier: str) -> str:
    """Render exactly one validated PostgreSQL identifier token."""

    value = validate_identifier(identifier)
    return '"' + value.replace('"', '""') + '"'


def quote_snowflake_identifier(identifier: str) -> str:
    """Render exactly one validated Snowflake identifier token."""

    value = validate_snowflake_identifier(identifier)
    return '"' + value.replace('"', '""') + '"'
