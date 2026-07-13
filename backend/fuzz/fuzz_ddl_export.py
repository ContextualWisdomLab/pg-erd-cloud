#!/usr/bin/env python3
"""Atheris harness for ``app.ddl.export.snapshot_json_to_sql``.

Untrusted-input surface: a captured schema *snapshot* (JSON produced by DB
introspection of a user-supplied database) is rendered into PostgreSQL /
Snowflake DDL. The renderer walks deeply nested, weakly-typed dicts and does
string surgery + regex rewriting on identifiers, types and default
expressions. It must be total over arbitrary snapshot shapes: only a bad
*dialect* is allowed to raise (documented ``ValueError``); a malformed snapshot
must still yield a string.

CodeGraph pointed here via:
    codegraph explore "DSN redaction parse sanitize identifier untrusted input"
    codegraph explore "snapshot_json_to_sql DDL export dialect mapping"

Run: python backend/fuzz/fuzz_ddl_export.py backend/fuzz/corpus/ddl_export
"""

from __future__ import annotations

import sys

import atheris

with atheris.instrument_imports():
    from app.ddl.export import snapshot_json_to_sql

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _snapshot import ByteFeeder, build_snapshot  # noqa: E402

_DIALECTS = ["postgresql", "snowflake", "pg", "sf", "postgres", "BOGUS", "", "x"]


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    feeder = ByteFeeder.from_fdp(fdp)
    snapshot = build_snapshot(feeder)
    dialect = _DIALECTS[fdp.ConsumeIntInRange(0, len(_DIALECTS) - 1)]

    try:
        out = snapshot_json_to_sql(snapshot, dialect)
    except ValueError:
        # Unsupported dialect is a documented, contract-level error.
        return

    if not isinstance(out, str):
        raise AssertionError(f"expected str output, got {type(out)!r}")

    # Determinism: a pure renderer must be referentially transparent.
    out2 = snapshot_json_to_sql(snapshot, dialect)
    if out != out2:
        raise AssertionError("snapshot_json_to_sql is non-deterministic")


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
