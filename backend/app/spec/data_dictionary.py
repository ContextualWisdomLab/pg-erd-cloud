"""Render a schema snapshot as a Markdown data dictionary.

Turns a captured snapshot (plus optional project table annotations) into
"living documentation": one section per table with columns, keys, indexes,
comments, example values, and any human-authored annotation.

Pure and dialect-agnostic -- it reads the common snapshot JSON shape produced
by the introspectors, so it works for both PostgreSQL and Snowflake snapshots.
"""

from __future__ import annotations

from typing import Any, Iterable


def _cell(value: object) -> str:
    """Render a value for a Markdown table cell (escape pipes/newlines)."""
    if value is None:
        return ""
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _relation_kind_label(kind: object) -> str:
    return {
        "r": "table",
        "v": "view",
        "m": "materialized view",
        "p": "partitioned table",
        "f": "foreign table",
    }.get(str(kind or ""), "table")


def _annotation_map(
    annotations: Iterable[dict[str, Any]] | None,
) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for ann in annotations or []:
        key = (str(ann.get("schema_name") or ""), str(ann.get("relation_name") or ""))
        body = ann.get("body")
        if body:
            result[key] = str(body)
    return result


def snapshot_to_data_dictionary_md(
    snapshot: dict[str, Any] | None,
    annotations: Iterable[dict[str, Any]] | None = None,
) -> str:
    """Return a Markdown data dictionary for one snapshot."""
    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    columns = snapshot.get("columns") or []
    pk_columns = snapshot.get("pk_columns") or []
    fk_edges = snapshot.get("fk_edges") or []
    indexes = snapshot.get("indexes") or []
    ann_by_table = _annotation_map(annotations)

    oid_to_rel: dict[Any, dict[str, Any]] = {
        rel.get("relation_oid"): rel for rel in relations
    }

    cols_by_oid: dict[Any, list[dict[str, Any]]] = {}
    for col in columns:
        cols_by_oid.setdefault(col.get("relation_oid"), []).append(col)
    for cols in cols_by_oid.values():
        cols.sort(key=lambda c: (c.get("column_position") or 0))

    pk_by_oid: dict[Any, set[str]] = {}
    for pk in pk_columns:
        name = pk.get("column_name")
        if name is not None:
            pk_by_oid.setdefault(pk.get("relation_oid"), set()).add(str(name))

    fk_child_cols: dict[Any, set[str]] = {}
    fk_by_oid: dict[Any, list[dict[str, Any]]] = {}
    for edge in fk_edges:
        oid = edge.get("child_relation_oid")
        fk_by_oid.setdefault(oid, []).append(edge)
        child_col = edge.get("child_column_name")
        if child_col is not None:
            fk_child_cols.setdefault(oid, set()).add(str(child_col))

    idx_by_oid: dict[Any, list[dict[str, Any]]] = {}
    for idx in indexes:
        idx_by_oid.setdefault(idx.get("relation_oid"), []).append(idx)

    out: list[str] = ["# Data Dictionary", ""]
    meta = []
    if snapshot.get("captured_at"):
        meta.append(f"Captured: {snapshot['captured_at']}")
    if snapshot.get("server_version"):
        meta.append(f"Server: {snapshot['server_version']}")
    if meta:
        out.append("_" + " · ".join(meta) + "_")
        out.append("")

    def _rel_sort_key(rel: dict[str, Any]) -> tuple[str, str]:
        return (str(rel.get("schema_name") or ""), str(rel.get("relation_name") or ""))

    if not relations:
        out.append("_No tables in this snapshot._")
        return "\n".join(out) + "\n"

    for rel in sorted(relations, key=_rel_sort_key):
        oid = rel.get("relation_oid")
        schema = str(rel.get("schema_name") or "")
        name = str(rel.get("relation_name") or "")
        out.append(f"## {schema}.{name}")
        kind = _relation_kind_label(rel.get("relation_kind"))
        if kind != "table":
            out.append(f"_{kind}_")
        if rel.get("relation_comment"):
            out.append(str(rel["relation_comment"]))
        note = ann_by_table.get((schema, name))
        if note:
            out.append(f"> 📝 {note}")
        out.append("")

        pks = pk_by_oid.get(oid, set())
        fk_cols = fk_child_cols.get(oid, set())
        out.append("| # | Column | Type | Null | Default | Key | Comment | Example |")
        out.append("|---|--------|------|------|---------|-----|---------|---------|")
        for i, col in enumerate(cols_by_oid.get(oid, []), start=1):
            col_name = str(col.get("column_name") or "")
            key_marks = []
            if col_name in pks:
                key_marks.append("PK")
            if col_name in fk_cols:
                key_marks.append("FK")
            nullable = "NOT NULL" if col.get("is_not_null") else ""
            default = col.get("default_expr") if col.get("has_default") else ""
            out.append(
                "| {i} | {name} | {type} | {null} | {default} | {key} | {comment} | {example} |".format(
                    i=i,
                    name=_cell(col_name),
                    type=_cell(col.get("data_type")),
                    null=nullable,
                    default=_cell(default),
                    key=" ".join(key_marks),
                    comment=_cell(col.get("column_comment")),
                    example=_cell(col.get("example_value")),
                )
            )
        out.append("")

        fks = fk_by_oid.get(oid, [])
        if fks:
            out.append("**Foreign keys:**")
            for edge in fks:
                parent = oid_to_rel.get(edge.get("parent_relation_oid"), {})
                parent_name = (
                    f"{parent.get('schema_name', '')}.{parent.get('relation_name', '')}"
                    if parent
                    else "?"
                )
                out.append(
                    f"- `{col_or_q(edge.get('child_column_name'))}` → "
                    f"`{parent_name}.{col_or_q(edge.get('parent_column_name'))}`"
                    + (f" ({edge['fk_constraint_name']})" if edge.get("fk_constraint_name") else "")
                )
            out.append("")

        idxs = [i for i in idx_by_oid.get(oid, []) if not i.get("is_primary")]
        if idxs:
            out.append("**Indexes:**")
            for idx in idxs:
                unique = "UNIQUE " if idx.get("is_unique") else ""
                out.append(f"- {unique}`{idx.get('index_name', '')}`")
            out.append("")

    return "\n".join(out).rstrip() + "\n"


def col_or_q(value: object) -> str:
    return str(value) if value is not None else "?"
