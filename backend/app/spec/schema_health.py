"""Detect schema smells from a snapshot -- a "schema health" report.

Reverse-engineering a database is most valuable when it also tells you what's
*wrong*: tables you can't safely replicate or update (no primary key), foreign
keys that will make joins slow (no supporting index), and tables that connect to
nothing (possible dead weight or a missing relationship). This turns a snapshot
into a prioritized findings list.

Pure and dialect-agnostic; matches by name/oid within the snapshot only.
"""

from __future__ import annotations

import re
from typing import Any

WARNING = "warning"
INFO = "info"

_SEVERITY_RANK = {WARNING: 0, INFO: 1}


def _index_columns(index_def: object) -> list[str]:
    """Best-effort column list from an index definition.

    ponytail: regex heuristic on the first ``(...)`` group. Expression indexes
    (e.g. ``lower(email)``) yield the raw expression, which simply won't match a
    plain FK column name -- acceptable for a "needs an index" hint.
    """
    text = str(index_def or "")
    match = re.search(r"\(([^()]*)\)", text)
    if not match:
        return []
    cols = []
    for part in match.group(1).split(","):
        token = part.strip().strip('"').split()  # drop ASC/DESC/opclass
        if token:
            cols.append(token[0].strip('"'))
    return cols


def _item(category: str, severity: str, target: str, detail: str) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "target": target,
        "detail": detail,
    }


def analyze_schema_health(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return schema-smell findings + a summary, most-severe first."""
    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    pk_columns = snapshot.get("pk_columns") or []
    fk_edges = snapshot.get("fk_edges") or []
    indexes = snapshot.get("indexes") or []

    def _qname(rel: dict[str, Any]) -> str:
        return f"{rel.get('schema_name')}.{rel.get('relation_name')}"

    # Only ordinary tables ('r') can meaningfully lack a PK / be orphaned.
    base_tables = {
        r.get("relation_oid"): r
        for r in relations
        if (r.get("relation_kind") or "r") == "r"
    }

    pk_oids: set[Any] = set()
    pk_cols_by_oid: dict[Any, set[str]] = {}
    for pk in pk_columns:
        oid = pk.get("relation_oid")
        pk_oids.add(oid)
        if pk.get("column_name") is not None:
            pk_cols_by_oid.setdefault(oid, set()).add(str(pk["column_name"]).lower())

    # Index first-columns per table (a FK is "covered" if it leads an index).
    index_lead_by_oid: dict[Any, set[str]] = {}
    for idx in indexes:
        oid = idx.get("relation_oid") or idx.get("table_oid")
        cols = _index_columns(idx.get("index_def"))
        if cols:
            index_lead_by_oid.setdefault(oid, set()).add(cols[0].lower())

    connected: set[Any] = set()
    for edge in fk_edges:
        connected.add(edge.get("child_relation_oid"))
        connected.add(edge.get("parent_relation_oid"))

    items: list[dict[str, Any]] = []

    for oid, rel in base_tables.items():
        if oid not in pk_oids:
            items.append(
                _item(
                    "no_primary_key", WARNING, _qname(rel),
                    "Table has no primary key — rows can't be uniquely addressed; blocks safe updates/replication.",
                )
            )
        if oid not in connected:
            items.append(
                _item(
                    "orphan_table", INFO, _qname(rel),
                    "Table has no foreign keys in or out — possibly disconnected or a missing relationship.",
                )
            )

    for edge in fk_edges:
        child_oid = edge.get("child_relation_oid")
        rel = base_tables.get(child_oid)
        if rel is None:
            continue
        col = str(edge.get("child_column_name") or "").lower()
        if not col:
            continue
        covered = col in pk_cols_by_oid.get(child_oid, set()) or col in index_lead_by_oid.get(child_oid, set())
        if not covered:
            items.append(
                _item(
                    "unindexed_foreign_key", WARNING,
                    f"{_qname(rel)}.{edge.get('child_column_name')}",
                    "Foreign key column has no supporting index — joins and cascading deletes will scan the whole table.",
                )
            )

    items.sort(key=lambda i: (_SEVERITY_RANK.get(i["severity"], 9), i["target"]))

    summary = {
        "warning": sum(1 for i in items if i["severity"] == WARNING),
        "info": sum(1 for i in items if i["severity"] == INFO),
        "total": len(items),
        "tables_analyzed": len(base_tables),
    }
    return {"items": items, "summary": summary}
