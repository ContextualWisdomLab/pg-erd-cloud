from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from sqlalchemy.engine import make_url


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


def build_admin_console_dsn(database_url: str, admin_database: str) -> str:
    """Build a sync DSN string for pooler admin consoles.

    Pooler admin consoles are typically exposed as virtual databases such as
    `pgbouncer` and `pgcat`. This helper rewrites an async SQLAlchemy URL into a
    sync DSN for psycopg, and sets the database name to the admin DB.
    """

    url = make_url(database_url)

    # psycopg expects a regular PostgreSQL URL; strip any SQLAlchemy driver.
    drivername = url.drivername
    if drivername.startswith("postgresql+"):
        drivername = "postgresql"

    next_url = url.set(drivername=drivername, database=admin_database)
    return str(next_url.render_as_string(hide_password=False))


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
