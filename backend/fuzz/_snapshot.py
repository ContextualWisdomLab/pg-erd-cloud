"""Shared helpers for building arbitrary ``snapshot`` dicts from fuzz bytes.

The snapshot is the untrusted structure that the DB introspection stage emits
and that the spec/DDL/naming generators consume. Every generator is supposed to
be *total* over arbitrary snapshot shapes -- it must never raise on malformed
input, only ever produce (possibly empty / noted) output. These helpers turn a
stream of fuzzer bytes into snapshot-shaped dicts with the keys and value types
the generators branch on, so the fuzzer spends its budget on interesting
structure rather than on rediscovering the top-level key names.

Works both with Atheris' ``FuzzedDataProvider`` (coverage-guided) and with a
plain deterministic PRNG (used by the Hypothesis / smoke fallbacks), so the
same corpus generation logic backs every harness.
"""

from __future__ import annotations

from typing import Any, Callable

# Value "kinds" the generators special-case: strings, ints, bools, None,
# nested dicts/lists, and single-char relation/constraint discriminators.
_REL_KINDS = ["r", "p", "v", "m", "f", "c", "t", "", "x"]
_CONSTRAINT_TYPES = ["p", "u", "c", "f", "x", ""]
_STRINGS = [
    "",
    "public",
    "orders",
    'weird"name',
    "a\x00b",
    "camelCase",
    "SELECT",
    "user",
    "x" * 80,
    "타이블",
    "numeric(10,2)",
    "character varying(255)",
    "timestamp with time zone",
    "'default'",
    "NEXTVAL('s')",
    "\n|pipe\n",
]


class ByteFeeder:
    """Uniform interface over Atheris FDP and a plain byte buffer."""

    def __init__(self, consume_int: Callable[[int], int]) -> None:
        self._consume_int = consume_int

    def choice(self, seq: list[Any]) -> Any:
        return seq[self._consume_int(len(seq) - 1)]

    def count(self, cap: int) -> int:
        return self._consume_int(cap)

    @classmethod
    def from_fdp(cls, fdp: Any) -> "ByteFeeder":
        return cls(lambda hi: fdp.ConsumeIntInRange(0, hi) if hi > 0 else 0)

    @classmethod
    def from_bytes(cls, data: bytes) -> "ByteFeeder":
        state = {"i": 0}

        def consume(hi: int) -> int:
            if hi <= 0:
                return 0
            if state["i"] >= len(data):
                return 0
            b = data[state["i"]]
            state["i"] += 1
            return b % (hi + 1)

        return cls(consume)


def _value(f: ByteFeeder, depth: int) -> Any:
    kind = f.count(7)
    if kind == 0:
        return f.choice(_STRINGS)
    if kind == 1:
        return f.choice([0, 1, -1, 2, 5, 63, 64, 2**31, -(2**31)])
    if kind == 2:
        return f.choice([True, False])
    if kind == 3:
        return None
    if kind == 4:
        return f.choice([1.5, 0.0, -3.25])
    if kind == 5 and depth < 2:
        return [_value(f, depth + 1) for _ in range(f.count(3))]
    if kind == 6 and depth < 2:
        return {f.choice(_STRINGS): _value(f, depth + 1) for _ in range(f.count(3))}
    return f.choice(_STRINGS)


def _relation(f: ByteFeeder) -> dict[str, Any]:
    return {
        "relation_oid": f.choice([1, 2, 3, 100, "bad", None]),
        "schema_name": f.choice(_STRINGS),
        "relation_name": f.choice(_STRINGS),
        "relation_kind": f.choice(_REL_KINDS),
        "tablespace_name": f.choice(_STRINGS + [None]),
        "is_partition": f.choice([True, False, None]),
        "partition_key": f.choice(_STRINGS + [None]),
        "partition_bound": f.choice(_STRINGS + [None]),
        "partition_parent_schema": f.choice(_STRINGS + [None]),
        "partition_parent_name": f.choice(_STRINGS + [None]),
    }


def _column(f: ByteFeeder) -> dict[str, Any]:
    return {
        "relation_oid": f.choice([1, 2, 3, 100, "bad", None]),
        "column_name": f.choice(_STRINGS),
        "column_position": f.choice([0, 1, 2, "bad", None]),
        "data_type": f.choice(_STRINGS + [None]),
        "domain_base_type": f.choice(_STRINGS + [None]),
        "array_dimensions": f.choice([0, 1, None]),
        "type_kind": f.choice(["e", "b", None]),
        "has_default": f.choice([True, False, None]),
        "default_expr": f.choice(_STRINGS + [None]),
        "is_not_null": f.choice([True, False, None]),
    }


def _constraint(f: ByteFeeder) -> dict[str, Any]:
    return {
        "relation_oid": f.choice([1, 2, 3, 100, "bad", None]),
        "schema_name": f.choice(_STRINGS),
        "relation_name": f.choice(_STRINGS),
        "constraint_name": f.choice(_STRINGS),
        "constraint_type": f.choice(_CONSTRAINT_TYPES),
        "constraint_def": f.choice(_STRINGS + [None]),
        "constrained_attnums": f.choice([[1, 2], [1], [], "bad", None, [1, "x"]]),
    }


def _index(f: ByteFeeder) -> dict[str, Any]:
    return {
        "index_def": f.choice(
            [
                "CREATE INDEX i ON t (a)",
                "CREATE UNIQUE INDEX i ON t (a)",
                "CREATE INDEX CONCURRENTLY i ON t (a)",
                "not an index",
                "",
            ]
            + [None]
        ),
        "index_name": f.choice(_STRINGS),
        "index_tablespace_name": f.choice(_STRINGS + [None]),
        "table_schema_name": f.choice(_STRINGS),
        "table_name": f.choice(_STRINGS),
    }


def build_snapshot(f: ByteFeeder) -> dict[str, Any]:
    """Assemble a snapshot dict shaped like DB-introspection output."""

    snapshot: dict[str, Any] = {
        "relations": [_relation(f) for _ in range(f.count(4))],
        "columns": [_column(f) for _ in range(f.count(5))],
        "constraints": [_constraint(f) for _ in range(f.count(4))],
        "indexes": [_index(f) for _ in range(f.count(3))],
        "fk_edges": [_value(f, 1) for _ in range(f.count(3))],
        "source_dialect": f.choice(
            ["postgresql", "snowflake", "pg", "sf", "bogus", None]
        ),
    }
    # Occasionally corrupt a top-level key to a wrong type to exercise the
    # isinstance guards in every generator.
    if f.count(4) == 0:
        snapshot["relations"] = f.choice(["not-a-list", None, 42])
    if f.count(4) == 0:
        snapshot["columns"] = f.choice([{}, None, "x"])
    return snapshot
