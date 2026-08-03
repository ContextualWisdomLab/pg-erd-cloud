"""Trusted-local PostgreSQL snapshot CLI.

The web API intentionally rejects loopback and private database targets. This
separate operator CLI accepts only an absolute Unix-domain socket directory, so
developers can reverse a local migration database without weakening the remote
API's SSRF boundary or putting a password-bearing DSN in the process list.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Sequence

import asyncpg

from app.pg_introspect.snapshot_collect import collect_postgres_snapshot

_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]{0,62}$")


def _socket_directory(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError(
            "--host must be an absolute PostgreSQL Unix socket directory"
        )
    if not path.is_dir():
        raise argparse.ArgumentTypeError("--host Unix socket directory does not exist")
    return str(path)


def _schema_name(value: str) -> str:
    if not _SCHEMA_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("--schema is not a valid PostgreSQL identifier")
    return value


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("--port must be between 1 and 65535")
    return port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pg-erd-snapshot",
        description=(
            "Write a pg-erd-cloud snapshot for a trusted local PostgreSQL Unix socket "
            "to stdout."
        ),
    )
    parser.add_argument(
        "--database",
        default=os.environ.get("PGDATABASE"),
        required=os.environ.get("PGDATABASE") is None,
        help="database name (defaults to PGDATABASE)",
    )
    parser.add_argument(
        "--host",
        type=_socket_directory,
        default=os.environ.get("PGHOST", "/tmp"),
        help="absolute Unix socket directory (defaults to PGHOST or /tmp)",
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=os.environ.get("PGPORT", "5432"),
        metavar="1..65535",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("PGUSER"),
        help="database user (defaults to PGUSER or the operating-system user)",
    )
    parser.add_argument("--schema", type=_schema_name, default=None)
    parser.add_argument("--pretty", action="store_true")
    return parser


async def capture_local_snapshot(args: argparse.Namespace) -> dict:
    connect_args: dict[str, object] = {
        "database": args.database,
        "host": args.host,
        "port": args.port,
        "timeout": 10,
    }
    if args.user:
        connect_args["user"] = args.user
    conn = await asyncpg.connect(**connect_args)
    try:
        return await collect_postgres_snapshot(conn, args.schema)
    finally:
        await conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        snapshot = asyncio.run(capture_local_snapshot(args))
    except (OSError, asyncpg.PostgresError) as exc:
        print(
            f"pg-erd-snapshot failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    json.dump(
        snapshot,
        sys.stdout,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
