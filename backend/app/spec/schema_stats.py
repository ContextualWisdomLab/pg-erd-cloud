"""Compute overview statistics for a schema snapshot.

A single call that answers "how big and how shaped is this schema?": object
counts, column distribution, the widest tables, PK/FK/index coverage, and the
most common data types. Useful for a dashboard header or an API consumer sizing
a migration effort.

Pure and dialect-agnostic.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

_KIND_LABELS = {
    "r": "table",
    "p": "table",  # partitioned table
    "v": "view",
    "m": "materialized_view",
    "f": "foreign_table",
    "t": "toast",
}


def compute_schema_stats(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return counts and distributions describing the snapshot."""
    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    columns = snapshot.get("columns") or []
    pk_columns = snapshot.get("pk_columns") or []
    fk_edges = snapshot.get("fk_edges") or []
    indexes = snapshot.get("indexes") or []

    rel_by_oid = {r.get("relation_oid"): r for r in relations}

    kinds: Counter[str] = Counter()
    for r in relations:
        kinds[_KIND_LABELS.get(r.get("relation_kind") or "r", "other")] += 1

    cols_per_oid: Counter[Any] = Counter()
    nullable = 0
    type_counts: Counter[str] = Counter()
    for c in columns:
        cols_per_oid[c.get("relation_oid")] += 1
        if not c.get("is_not_null"):
            nullable += 1
        dtype = str(c.get("data_type") or "").strip().lower()
        if dtype:
            type_counts[dtype] += 1

    table_oids = [
        r.get("relation_oid")
        for r in relations
        if (r.get("relation_kind") or "r") in ("r", "p")
    ]
    pk_oids = {pk.get("relation_oid") for pk in pk_columns}
    without_pk = sum(1 for oid in table_oids if oid not in pk_oids)

    total_columns = len(columns)
    table_total = len(table_oids)

    def _qname(oid: Any) -> str:
        rel = rel_by_oid.get(oid) or {}
        return f"{rel.get('schema_name')}.{rel.get('relation_name')}"

    widest = [
        {"table": _qname(oid), "columns": n}
        for oid, n in cols_per_oid.most_common(5)
    ]

    return {
        "relations": {**dict(kinds), "total": len(relations)},
        "columns": {
            "total": total_columns,
            "nullable": nullable,
            "not_null": total_columns - nullable,
            "avg_per_table": round(total_columns / table_total, 1) if table_total else 0.0,
            "max_per_table": max(cols_per_oid.values(), default=0),
        },
        "constraints": {
            "primary_keys": len(pk_oids),
            "foreign_keys": len(fk_edges),
            "indexes": len(indexes),
        },
        "tables_without_primary_key": without_pk,
        "widest_tables": widest,
        "data_types": dict(type_counts.most_common(10)),
    }
