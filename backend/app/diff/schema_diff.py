"""Diff two schema snapshots into a structured change set.

Snapshots are the JSON payloads captured by reverse-engineering a database
(see ``SchemaSnapshotData.snapshot_json``): ``relations``, ``columns``,
``pk_columns`` and ``fk_edges``, all keyed internally by ``relation_oid``.

IMPORTANT: ``relation_oid`` (and ``fk_constraint_oid``) are database-internal
identifiers that are re-assigned on every introspection run. Two snapshots of
the *same* database therefore have *different* oids for the *same* table, so we
must never diff by oid. Instead we key tables by ``(schema_name, relation_name)``
and columns by name, and we resolve every FK's oids to table names *within its
own snapshot* before comparing. Diffing by oid would report every table as
changed on each run — a silent, high-impact bug.
"""

from __future__ import annotations

from typing import Any


def _table_key(schema_name: object, relation_name: object) -> str:
    schema = str(schema_name) if schema_name is not None else ""
    name = str(relation_name) if relation_name is not None else ""
    return f"{schema}.{name}" if schema else name


def _index_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Build name-keyed lookups for one snapshot (oid-independent)."""

    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    columns = snapshot.get("columns") or []
    pk_columns = snapshot.get("pk_columns") or []
    fk_edges = snapshot.get("fk_edges") or []

    oid_to_table: dict[Any, str] = {}
    tables: dict[str, dict[str, Any]] = {}
    for rel in relations:
        key = _table_key(rel.get("schema_name"), rel.get("relation_name"))
        oid_to_table[rel.get("relation_oid")] = key
        tables[key] = {
            "schema_name": str(rel.get("schema_name") or ""),
            "relation_name": str(rel.get("relation_name") or ""),
            "comment": rel.get("relation_comment"),
            "kind": rel.get("relation_kind"),
            "columns": {},
            "pk": [],
        }

    for col in columns:
        table = oid_to_table.get(col.get("relation_oid"))
        if table is None or table not in tables:
            continue
        name = col.get("column_name")
        if name is None:
            continue
        indexed_column = {
            "data_type": col.get("data_type"),
            "is_not_null": bool(col.get("is_not_null")),
        }
        if "has_default" in col or "default_expr" in col:
            indexed_column.update(
                {
                    "has_default": bool(col.get("has_default")),
                    "default_expr": col.get("default_expr"),
                }
            )
        tables[table]["columns"][str(name)] = indexed_column

    # Preserve primary-key column order via column_ordinal when present.
    pk_tmp: dict[str, list[tuple[int, str]]] = {}
    for pk in pk_columns:
        table = oid_to_table.get(pk.get("relation_oid"))
        if table is None or table not in tables:
            continue
        name = pk.get("column_name")
        if name is None:
            continue
        ordinal = pk.get("column_ordinal")
        ordinal = int(ordinal) if isinstance(ordinal, int) else len(pk_tmp.get(table, []))
        pk_tmp.setdefault(table, []).append((ordinal, str(name)))
    for table, items in pk_tmp.items():
        items.sort(key=lambda pair: pair[0])
        tables[table]["pk"] = [name for _, name in items]

    # Resolve FK oids to (child_table, child_col -> parent_table, parent_col).
    # Group multi-column FKs by constraint via a stable resolved signature.
    fk_parts: dict[tuple[str, str, str], list[tuple[int, str, str]]] = {}
    for edge in fk_edges:
        child = oid_to_table.get(edge.get("child_relation_oid"))
        parent = oid_to_table.get(edge.get("parent_relation_oid"))
        if child is None or parent is None:
            continue
        name = str(edge.get("fk_constraint_name") or "")
        ordinal = edge.get("column_ordinal")
        ordinal = int(ordinal) if isinstance(ordinal, int) else 0
        fk_parts.setdefault((child, parent, name), []).append(
            (
                ordinal,
                str(edge.get("child_column_name") or ""),
                str(edge.get("parent_column_name") or ""),
            )
        )

    fks: dict[str, dict[str, Any]] = {}
    for (child, parent, name), parts in fk_parts.items():
        parts.sort(key=lambda p: p[0])
        child_cols = [c for _, c, _ in parts]
        parent_cols = [p for _, _, p in parts]
        # Signature is oid-independent: names + column pairing, not the FK name
        # (constraint names may auto-generate differently between runs).
        signature = (
            f"{child}({','.join(child_cols)})->"
            f"{parent}({','.join(parent_cols)})"
        )
        fks[signature] = {
            "name": name or None,
            "child_table": child,
            "child_columns": child_cols,
            "parent_table": parent,
            "parent_columns": parent_cols,
        }

    return {"tables": tables, "fks": fks}


def _diff_columns(
    base_cols: dict[str, Any], target_cols: dict[str, Any]
) -> dict[str, Any]:
    base_names = set(base_cols)
    target_names = set(target_cols)
    added = sorted(target_names - base_names)
    removed = sorted(base_names - target_names)
    changed: list[dict[str, Any]] = []
    for name in sorted(base_names & target_names):
        before = base_cols[name]
        after = target_cols[name]
        if before != after:
            changed.append({"column": name, "from": before, "to": after})
    return {"added": added, "removed": removed, "changed": changed}


def diff_snapshots(
    base: dict[str, Any] | None, target: dict[str, Any] | None
) -> dict[str, Any]:
    """Compute a structured diff from ``base`` to ``target`` snapshot JSON.

    Both arguments are snapshot ``snapshot_json`` payloads (or ``None``). The
    result reports table/column/primary-key/foreign-key changes plus a summary.
    All matching is by name, so it is stable across introspection runs.
    """

    b = _index_snapshot(base)
    t = _index_snapshot(target)

    base_tables = set(b["tables"])
    target_tables = set(t["tables"])

    tables_added = sorted(target_tables - base_tables)
    tables_removed = sorted(base_tables - target_tables)

    changed_tables: list[dict[str, Any]] = []
    columns_added = columns_removed = columns_changed = 0
    for table in sorted(base_tables & target_tables):
        bt = b["tables"][table]
        tt = t["tables"][table]
        col_diff = _diff_columns(bt["columns"], tt["columns"])
        pk_changed = bt["pk"] != tt["pk"]
        comment_changed = bt["comment"] != tt["comment"]
        if (
            col_diff["added"]
            or col_diff["removed"]
            or col_diff["changed"]
            or pk_changed
            or comment_changed
        ):
            columns_added += len(col_diff["added"])
            columns_removed += len(col_diff["removed"])
            columns_changed += len(col_diff["changed"])
            entry: dict[str, Any] = {"table": table, "columns": col_diff}
            if pk_changed:
                entry["primary_key"] = {"from": bt["pk"], "to": tt["pk"]}
            if comment_changed:
                entry["comment"] = {"from": bt["comment"], "to": tt["comment"]}
            changed_tables.append(entry)

    base_fks = set(b["fks"])
    target_fks = set(t["fks"])
    fks_added = sorted(target_fks - base_fks)
    fks_removed = sorted(base_fks - target_fks)

    summary = {
        "tables_added": len(tables_added),
        "tables_removed": len(tables_removed),
        "tables_changed": len(changed_tables),
        "columns_added": columns_added,
        "columns_removed": columns_removed,
        "columns_changed": columns_changed,
        "fks_added": len(fks_added),
        "fks_removed": len(fks_removed),
    }
    summary["has_changes"] = any(v for k, v in summary.items() if k != "has_changes")

    return {
        "base_table_count": len(base_tables),
        "target_table_count": len(target_tables),
        "tables": {
            "added": tables_added,
            "removed": tables_removed,
            "changed": changed_tables,
        },
        "foreign_keys": {
            "added": [t["fks"][s] for s in fks_added],
            "removed": [b["fks"][s] for s in fks_removed],
        },
        "summary": summary,
    }
