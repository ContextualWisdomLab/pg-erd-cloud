from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from sqlalchemy.engine import URL, make_url


class PoolerKind(str, Enum):
    """Known PostgreSQL connection poolers."""

    PGBOUNCER = "pgbouncer"
    PGCAT = "pgcat"
    UNKNOWN = "unknown"
    NONE = "none"


ReadRoutingMode = Literal["off", "auto", "on"]


@dataclass(frozen=True)
class PoolerDetectionResult:
    """Best-effort pooler detection output."""

    kind: PoolerKind
    detected: bool
    version_text: str | None


def classify_pooler_version_text(version_text: str) -> PoolerKind:
    """Classify a pooler based on SHOW VERSION output."""
    text = version_text.strip().lower()
    if "pgbouncer" in text:
        return PoolerKind.PGBOUNCER
    if "pgcat" in text:
        return PoolerKind.PGCAT
    return PoolerKind.UNKNOWN


def build_admin_console_dsn(
    database_url: str, admin_database: str
) -> tuple[str, str | None]:
    """Build a sync DSN (without password) for pooler admin consoles.

    Pooler admin consoles are typically exposed as virtual databases such as
    `pgbouncer` and `pgcat`. This helper rewrites an async SQLAlchemy URL into a
    sync DSN for psycopg, and sets the database name to the admin DB.
    """

    url = make_url(database_url)

    # psycopg expects a regular PostgreSQL URL; strip any SQLAlchemy driver.
    drivername = url.drivername
    if drivername.startswith("postgresql+"):
        drivername = "postgresql"

    # Avoid embedding credentials in DSN strings. Some drivers/loggers may echo
    # DSNs, so keep the password separate.
    password = url.password

    # NOTE: URL.set(password=None) does not clear the password; it leaves it as
    # is. Construct a fresh URL to ensure the password is omitted.
    safe_url = URL.create(
        drivername=drivername,
        username=url.username,
        password=None,
        host=url.host,
        port=url.port,
        database=admin_database,
        query=url.query,
    )

    # Render as a string with password redaction enabled (defense-in-depth).
    dsn = str(safe_url.render_as_string(hide_password=True))
    return dsn, password


def should_route_reads_to_read_only(
    *,
    mode: ReadRoutingMode,
    read_only_url: str | None,
    pooler_detected: bool,
) -> bool:
    """Decide whether a read-only session should use the read-only DSN."""

    if not read_only_url:
        return False

    if mode == "off":
        return False
    if mode == "on":
        return True
    # mode == "auto"
    return pooler_detected
