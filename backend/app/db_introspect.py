from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from app.dsn_redaction import redact_dsn_error_message
from app.pg_introspect.introspect import introspect_postgres
from app.snowflake_introspect import introspect_snowflake

DatabaseDialect = Literal["postgresql", "snowflake"]


def detect_dsn_dialect(dsn: str) -> DatabaseDialect:
    """Infer the source database dialect from a connection string scheme."""

    scheme = urlparse(dsn).scheme.lower().split("+", 1)[0]
    if scheme in ("postgres", "postgresql"):
        return "postgresql"
    if scheme == "snowflake":
        return "snowflake"
    raise ValueError(f"unsupported database DSN scheme: {scheme or '<empty>'}")


async def introspect_database(dsn: str, schema_filter: str | None) -> dict:
    """Introspect a supported database and return the common snapshot JSON."""

    try:
        dialect = detect_dsn_dialect(dsn)
        if dialect == "snowflake":
            return await introspect_snowflake(dsn, schema_filter)
        return await introspect_postgres(dsn, schema_filter)
    except Exception as exc:
        message = str(exc) or type(exc).__name__
        raise RuntimeError(redact_dsn_error_message(message, dsn)) from None
