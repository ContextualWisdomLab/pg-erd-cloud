#!/usr/bin/env python3
"""Atheris harness for the pure DSN-parsing helpers in the SSRF guard.

Untrusted-input surface: ``app.pg_introspect.dsn_guard`` is the SSRF gate for
user-supplied PostgreSQL DSNs. Its network-touching path (DNS + allowlist)
needs settings and sockets, but the *parsing* helpers that decide host/port
targets are pure and run on fully attacker-controlled strings. Their contract:
they must only ever raise ``DsnTargetError`` (a ``ValueError`` subclass) on bad
input -- never ``IndexError``/``TypeError``/etc, which would escape the guard's
handling. ``_parse_ip_literal`` must never raise at all, and a literal it
accepts must be classifiable as restricted-or-not without raising.

CodeGraph pointed here via:
    codegraph explore "validate_postgres_dsn_target dsn guard SSRF host port parse"

Run: python backend/fuzz/fuzz_dsn_guard.py backend/fuzz/corpus/dsn_guard
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

# app.settings (imported transitively by dsn_guard) needs these; use dummy,
# non-secret defaults so the harness is hermetic (never reads real secrets).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://fuzz:fuzz@127.0.0.1:5432/fuzz",
)
os.environ.setdefault("APP_SECRET", "fuzz-not-a-secret")
os.environ.setdefault("DB_INTROSPECTION_ALLOWED_HOSTS", "db.example.com,*.example.net")

import atheris  # noqa: E402

with atheris.instrument_imports():
    from app.pg_introspect import dsn_guard


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    raw = fdp.ConsumeUnicodeNoSurrogates(512)

    # Query-param + port + host splitting: only DsnTargetError is allowed.
    parsed = urlparse(raw)
    try:
        params = dsn_guard._parse_query_params(parsed.query)
        dsn_guard._validate_query_ports(params.get("port", []))
        dsn_guard._split_query_host_values(params.get("host", []), "host")
        dsn_guard._split_query_host_values(params.get("hostaddr", []), "hostaddr")
    except dsn_guard.DsnTargetError:
        pass  # contract-level rejection

    # IP-literal parsing must be total and its result classifiable.
    host_token = fdp.ConsumeUnicodeNoSurrogates(64)
    literal = dsn_guard._parse_ip_literal(host_token)
    if literal is not None:
        dsn_guard._is_restricted_ip(literal)
        dsn_guard._connection_host_for_ip(literal)

    # Allowlist matcher must be total over arbitrary host/entry pairs.
    entry = fdp.ConsumeUnicodeNoSurrogates(32)
    dsn_guard._host_matches_allowed_entry(host_token.lower(), entry.lower())


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
