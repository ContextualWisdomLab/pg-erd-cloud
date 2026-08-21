"""Infer *implicit* foreign-key relationships from a schema snapshot.

Many real databases -- especially legacy or analytics schemas -- never declare
their foreign keys. Reverse-engineering those relationships is the core reason
to reach for a schema-intelligence tool over a generic ERD drawer.

The heuristic is deliberately high-precision (favouring few false positives):
a column named ``<X>_id`` is a likely FK to a table named ``X`` (or its simple
plural) that has a primary key, when the column is not *already* a declared FK.
Confidence is ``high`` when the column type matches the referenced key's type,
otherwise ``medium``.

Pure and dialect-agnostic (reads the common snapshot JSON shape).
"""

from __future__ import annotations

import re
from typing import Any


def _norm_type(data_type: object) -> str:
    """Normalize a SQL type for comparison (drop length/precision modifiers)."""
    text = str(data_type or "").strip().lower()
    text = re.sub(r"\(.*?\)", "", text)  # varchar(100) -> varchar
    return re.sub(r"\s+", " ", text).strip()


def _candidate_target_names(base: str) -> set[str]:
    base = base.lower()
    names = {base, base + "s", base + "es"}
    if base.endswith("y"):
        names.add(base[:-1] + "ies")
    return names


def infer_relationships(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return inferred (undeclared) foreign-key relationships, sorted stably."""
    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    columns = snapshot.get("columns") or []
    pk_columns = snapshot.get("pk_columns") or []
    fk_edges = snapshot.get("fk_edges") or []

    rel_by_oid: dict[Any, dict[str, Any]] = {r.get("relation_oid"): r for r in relations}

    # relation_name (lower) -> list of relation dicts (there may be same name in
    # multiple schemas; we only infer within the same schema to avoid noise).
    by_name: dict[str, list[dict[str, Any]]] = {}
    for r in relations:
        by_name.setdefault(str(r.get("relation_name") or "").lower(), []).append(r)

    cols_by_oid: dict[Any, dict[str, dict[str, Any]]] = {}
    for c in columns:
        name = c.get("column_name")
        if name is None:
            continue
        cols_by_oid.setdefault(c.get("relation_oid"), {})[str(name).lower()] = c

    pk_by_oid: dict[Any, list[str]] = {}
    for pk in pk_columns:
        name = pk.get("column_name")
        if name is not None:
            pk_by_oid.setdefault(pk.get("relation_oid"), []).append(str(name).lower())

    declared: set[tuple[Any, str]] = set()
    for edge in fk_edges:
        col = edge.get("child_column_name")
        if col is not None:
            declared.add((edge.get("child_relation_oid"), str(col).lower()))

    def _ref_column(target_oid: Any, child_col: str) -> str | None:
        target_cols = cols_by_oid.get(target_oid, {})
        pks = pk_by_oid.get(target_oid, [])
        if len(pks) == 1 and pks[0] in target_cols:
            return pks[0]
        if child_col in target_cols:  # e.g. orders.member_id -> member.member_id
            return child_col
        if "id" in target_cols:
            return "id"
        return None

    results: list[dict[str, Any]] = []
    seen: set[tuple[Any, str, Any, str]] = set()

    for child in relations:
        child_oid = child.get("relation_oid")
        child_schema = str(child.get("schema_name") or "")
        for col_name_lower, col in cols_by_oid.get(child_oid, {}).items():
            if not col_name_lower.endswith("_id") or len(col_name_lower) <= 3:
                continue
            if (child_oid, col_name_lower) in declared:
                continue
            base = col_name_lower[:-3]
            if not base:
                continue
            candidates = _candidate_target_names(base)
            for cand in candidates:
                for target in by_name.get(cand, []):
                    target_oid = target.get("relation_oid")
                    if str(target.get("schema_name") or "") != child_schema:
                        continue
                    if not pk_by_oid.get(target_oid):
                        continue
                    ref = _ref_column(target_oid, col_name_lower)
                    if ref is None:
                        continue
                    # A table's own PK named "<table>_id" is the key itself,
                    # not a self-referencing foreign key.
                    if target_oid == child_oid and ref == col_name_lower:
                        continue
                    key = (child_oid, col_name_lower, target_oid, ref)
                    if key in seen:
                        continue
                    seen.add(key)
                    ref_col = cols_by_oid.get(target_oid, {}).get(ref, {})
                    same_type = _norm_type(col.get("data_type")) == _norm_type(
                        ref_col.get("data_type")
                    )
                    results.append(
                        {
                            "child_schema": child_schema,
                            "child_table": str(child.get("relation_name") or ""),
                            "child_column": str(col.get("column_name") or ""),
                            "parent_schema": str(target.get("schema_name") or ""),
                            "parent_table": str(target.get("relation_name") or ""),
                            "parent_column": ref,
                            "confidence": "high" if same_type else "medium",
                            "reason": (
                                f"column '{col.get('column_name')}' matches table "
                                f"'{target.get('relation_name')}'"
                                + ("" if same_type else " (type differs)")
                            ),
                        }
                    )

    results.sort(
        key=lambda r: (
            r["child_schema"],
            r["child_table"],
            r["child_column"],
            r["parent_table"],
        )
    )
    return results
