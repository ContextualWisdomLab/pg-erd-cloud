"""Property-based (Hypothesis) fuzz tests for untrusted-input surfaces.

These complement the coverage-guided Atheris harnesses in ``backend/fuzz/``.
Hypothesis (MPL-2.0) is not part of the pinned runtime/dev lock, so this module
is skipped in the normal hash-locked test job via ``importorskip`` and exercises
the same invariants wherever Hypothesis is installed.

Surfaces (all pure, deterministic, network-free) identified with CodeGraph:
  * app.sanitize.sanitize_for_storage        -- NUL-stripping storage guard
  * app.ddl.export.snapshot_json_to_sql      -- snapshot -> DDL renderer
  * app.spec.reversing / index_design        -- snapshot -> spec/prompt
  * app.spec.naming_lint / wide_tables       -- snapshot -> findings report
  * app.dsn_redaction.redact_dsn_error_message -- secret redaction
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from app.ddl.export import snapshot_json_to_sql  # noqa: E402
from app.dsn_redaction import redact_dsn_error_message  # noqa: E402
from app.sanitize import sanitize_for_storage, strip_nul  # noqa: E402
from app.spec.index_design import generate_index_design_spec  # noqa: E402
from app.spec.naming_lint import lint_naming  # noqa: E402
from app.spec.reversing import generate_reversing_spec  # noqa: E402
from app.spec.wide_tables import detect_wide_tables  # noqa: E402

_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

# --- strategies ------------------------------------------------------------

_SCALAR = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**33), max_value=2**33),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(max_size=40),
    st.binary(max_size=20),
)

# Free-form string surface -- the values a hostile *database* actually controls
# (identifier names, type text, default expressions, index/constraint DDL). Kept
# maximally adversarial: NUL, quotes, pipes, newlines, oversized, non-ASCII.
_HOSTILE_TEXT = st.one_of(
    st.none(),
    st.text(max_size=80),
    st.sampled_from(
        [
            'weird"name',
            "a\x00b",
            "SELECT",
            "user",
            "numeric(10,2)",
            "character varying(255)",
            "timestamp with time zone",
            "'default'",
            "NEXTVAL('s')",
            "\n|pipe|\n",
            "타이블",
            "x" * 100,
        ]
    ),
)
# Integer-or-None: fields DB introspection always emits as OIDs / ordinals.
_OID = st.one_of(st.none(), st.integers(min_value=-5, max_value=500))
_BOOLISH = st.one_of(st.none(), st.booleans())


@st.composite
def _row(draw: st.DrawFn) -> dict:
    """A snapshot row: id-like fields are int|None (as pg emits), name/type/
    definition fields are fully hostile strings -- the real fuzz surface."""

    row = {
        "relation_oid": draw(_OID),
        "schema_name": draw(_HOSTILE_TEXT),
        "relation_name": draw(_HOSTILE_TEXT),
        "relation_kind": draw(
            st.sampled_from(["r", "p", "v", "m", "f", "c", "", "x", None])
        ),
        "column_name": draw(_HOSTILE_TEXT),
        "column_position": draw(_OID),
        "data_type": draw(_HOSTILE_TEXT),
        "domain_base_type": draw(_HOSTILE_TEXT),
        "is_not_null": draw(_BOOLISH),
        "has_default": draw(_BOOLISH),
        "default_expr": draw(_HOSTILE_TEXT),
        "constraint_type": draw(st.sampled_from(["p", "u", "c", "f", "x", "", None])),
        "constraint_name": draw(_HOSTILE_TEXT),
        "constraint_def": draw(_HOSTILE_TEXT),
        "constrained_attnums": draw(
            st.one_of(st.none(), st.lists(_OID, max_size=5))
        ),
        "index_def": draw(_HOSTILE_TEXT),
        "index_name": draw(_HOSTILE_TEXT),
        "index_tablespace_name": draw(_HOSTILE_TEXT),
        "table_name": draw(_HOSTILE_TEXT),
        "table_schema_name": draw(_HOSTILE_TEXT),
        "tablespace_name": draw(_HOSTILE_TEXT),
        "is_partition": draw(_BOOLISH),
        "partition_key": draw(_HOSTILE_TEXT),
        "partition_bound": draw(_HOSTILE_TEXT),
        "partition_parent_schema": draw(_HOSTILE_TEXT),
        "partition_parent_name": draw(_HOSTILE_TEXT),
    }
    # Randomly drop keys so missing-field paths are exercised too.
    drop = draw(st.sets(st.sampled_from(sorted(row)), max_size=6))
    return {k: v for k, v in row.items() if k not in drop}


_ROWS = st.lists(_row(), max_size=8)


@st.composite
def _snapshots(draw: st.DrawFn) -> dict:
    # Usually a well-formed list-of-rows; occasionally a wrong-typed top-level
    # value, to prove the generators tolerate malformed JSON.
    def key(strat):
        return draw(
            st.one_of(strat, st.none(), st.text(max_size=5), st.integers())
            if draw(st.integers(0, 9)) == 0
            else strat
        )

    return {
        "relations": key(_ROWS),
        "columns": key(_ROWS),
        "constraints": key(_ROWS),
        "indexes": key(_ROWS),
        "fk_edges": key(_ROWS),
        "source_dialect": draw(
            st.sampled_from(["postgresql", "snowflake", "pg", "sf", "bogus", None])
        ),
    }


# --- sanitize --------------------------------------------------------------


def _no_nul(obj: object) -> bool:
    if isinstance(obj, str):
        return "\x00" not in obj
    if isinstance(obj, Mapping):
        return all(_no_nul(k) and _no_nul(v) for k, v in obj.items())
    if isinstance(obj, (list, tuple)):
        return all(_no_nul(v) for v in obj)
    return True


@_SETTINGS
@given(
    st.recursive(
        _SCALAR,
        lambda children: st.one_of(
            st.lists(children, max_size=5),
            st.dictionaries(st.text(max_size=10), children, max_size=5),
        ),
        max_leaves=25,
    )
)
def test_sanitize_removes_all_nul(value: object) -> None:
    """No NUL byte may survive anywhere in the sanitized structure."""
    assert _no_nul(sanitize_for_storage(value))


@_SETTINGS
@given(st.text(max_size=200))
def test_strip_nul_is_idempotent(text: str) -> None:
    once = strip_nul(text)
    assert "\x00" not in once
    assert strip_nul(once) == once


# --- snapshot generators: totality + determinism ---------------------------


@_SETTINGS
@given(_snapshots(), st.sampled_from(["postgresql", "snowflake", "pg", "sf"]))
def test_ddl_export_total_and_deterministic(snapshot: dict, dialect: str) -> None:
    out = snapshot_json_to_sql(snapshot, dialect)
    assert isinstance(out, str)
    assert out == snapshot_json_to_sql(snapshot, dialect)


@_SETTINGS
@given(_snapshots(), st.sampled_from(["markdown", "llm-prompt"]))
def test_spec_generators_total_and_deterministic(snapshot: dict, mode: str) -> None:
    for fn in (generate_reversing_spec, generate_index_design_spec):
        out = fn(snapshot, mode)
        assert isinstance(out, str)
        assert out == fn(snapshot, mode)


@_SETTINGS
@given(_snapshots())
def test_naming_lint_summary_is_consistent(snapshot: dict) -> None:
    report = lint_naming(snapshot)
    items = report["items"]
    summary = report["summary"]
    assert summary["total"] == len(items)
    assert summary["high"] == sum(1 for i in items if i["severity"] == "high")
    assert summary["info"] == sum(1 for i in items if i["severity"] == "info")


@_SETTINGS
@given(_snapshots())
def test_wide_tables_total(snapshot: dict) -> None:
    assert isinstance(detect_wide_tables(snapshot), dict)


# --- dsn redaction: crash safety + no secret leak --------------------------

_SAFE_PW = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.~",
    min_size=1,
    max_size=40,
)


@_SETTINGS
@given(st.text(max_size=256), st.text(max_size=256))
def test_redact_never_crashes(error_message: str, dsn: str) -> None:
    assert isinstance(redact_dsn_error_message(error_message, dsn), str)


@_SETTINGS
@given(_SAFE_PW, st.text(max_size=120))
def test_redact_does_not_leak_password(pw: str, noise: str) -> None:
    dsn = f"postgresql://user:{pw}@db.example.com:5432/app?sslmode=require"
    message = f"connection failed: {noise} password={pw} connecting to {dsn}"
    redacted = redact_dsn_error_message(message, dsn)
    assert f"password={pw}" not in redacted
    assert f":{pw}@" not in redacted
