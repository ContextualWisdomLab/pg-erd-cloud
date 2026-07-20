"""Classify the risk of each change between two schema snapshots.

Teams don't fear *writing* a migration -- they fear running it in production:
data loss (dropping a table/column), long table locks (rewriting a column
type, validating a new FK), or a migration that simply fails against real data
(``SET NOT NULL`` with existing NULLs). This module turns a diff into a
severity-classified risk report so a reviewer can see, before applying, exactly
which statements are dangerous and why.

Pure and dialect-agnostic; matches tables/columns/FKs by name (never the
volatile ``relation_oid``), reusing the diff indexer.
"""

from __future__ import annotations

from typing import Any

from app.diff.schema_diff import _index_snapshot

SAFE = "safe"
WARNING = "warning"
DESTRUCTIVE = "destructive"

_SEVERITY_RANK = {DESTRUCTIVE: 0, WARNING: 1, SAFE: 2}


def _item(
    category: str,
    severity: str,
    target: str,
    detail: str,
    **evidence: object,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "category": category,
        "severity": severity,
        "target": target,
        "detail": detail,
    }
    item.update(evidence)
    return item


def _fk_label(fk: dict[str, Any]) -> str:
    child_cols = ", ".join(fk.get("child_columns") or [])
    return f"{fk.get('child_table')}({child_cols}) -> {fk.get('parent_table')}"


def analyze_migration_safety(
    base: dict[str, Any] | None, target: dict[str, Any] | None
) -> dict[str, Any]:
    """Return risk-classified changes to migrate *base* to *target*."""
    b = _index_snapshot(base)
    t = _index_snapshot(target)
    b_tables, t_tables = b["tables"], t["tables"]
    items: list[dict[str, Any]] = []

    for key, tbl in b_tables.items():
        if key not in t_tables:
            items.append(
                _item("drop_table", DESTRUCTIVE, key, "Table is dropped — all its data is lost.")
            )
    for key, tbl in t_tables.items():
        if key not in b_tables:
            items.append(_item("create_table", SAFE, key, "New table."))

    for key, ttbl in t_tables.items():
        if key not in b_tables:
            continue
        btbl = b_tables[key]
        b_cols, t_cols = btbl["columns"], ttbl["columns"]

        for name, col in t_cols.items():
            if name in b_cols:
                continue
            if col.get("is_not_null"):
                has_default = bool(col.get("has_default"))
                items.append(
                    _item(
                        "add_column", WARNING, f"{key}.{name}",
                        (
                            "New NOT NULL column; a default is present, but its "
                            "volatility, backfill, and table-lock behavior still "
                            "need dialect-specific verification."
                            if has_default
                            else "New NOT NULL column without a default — fails "
                            "or locks if the table has rows."
                        ),
                        has_default=has_default,
                    )
                )
            else:
                items.append(_item("add_column", SAFE, f"{key}.{name}", "New nullable column."))
        for name in b_cols:
            if name not in t_cols:
                items.append(
                    _item("drop_column", DESTRUCTIVE, f"{key}.{name}", "Column dropped — its data is lost.")
                )
        for name, col in t_cols.items():
            if name not in b_cols:
                continue
            old = b_cols[name]
            if (old.get("data_type") or "") != (col.get("data_type") or ""):
                items.append(
                    _item(
                        "alter_column_type", WARNING, f"{key}.{name}",
                        f"Type {old.get('data_type')} -> {col.get('data_type')} may rewrite/lock the table and can fail on incompatible data.",
                    )
                )
            if not old.get("is_not_null") and col.get("is_not_null"):
                items.append(
                    _item(
                        "set_not_null", WARNING, f"{key}.{name}",
                        "SET NOT NULL scans the whole table and fails if existing NULLs are present.",
                    )
                )
            if old.get("is_not_null") and not col.get("is_not_null"):
                items.append(_item("drop_not_null", SAFE, f"{key}.{name}", "Relaxing NOT NULL is safe."))
            old_has_default = bool(old.get("has_default"))
            new_has_default = bool(col.get("has_default"))
            if not old_has_default and new_has_default:
                items.append(
                    _item(
                        "set_default",
                        SAFE,
                        f"{key}.{name}",
                        "Adding a column default affects future rows and does not remove existing data.",
                    )
                )
            elif old_has_default and not new_has_default:
                items.append(
                    _item(
                        "drop_default",
                        SAFE,
                        f"{key}.{name}",
                        "Dropping a column default affects future rows and does not remove existing data.",
                    )
                )
            elif (
                old_has_default
                and new_has_default
                and old.get("default_expr") != col.get("default_expr")
            ):
                items.append(
                    _item(
                        "alter_default",
                        SAFE,
                        f"{key}.{name}",
                        "Changing a column default affects future rows and does not remove existing data.",
                    )
                )

        if btbl.get("pk", []) != ttbl.get("pk", []):
            items.append(
                _item(
                    "primary_key_change", DESTRUCTIVE, key,
                    "Primary key changed — usually needs data-aware handling and can lock the table.",
                )
            )

    base_fks, target_fks = b["fks"], t["fks"]
    for sig, fk in target_fks.items():
        if sig not in base_fks:
            items.append(
                _item(
                    "add_foreign_key", WARNING, _fk_label(fk),
                    "New foreign key validates all existing rows (brief lock) and fails if data violates it.",
                )
            )
    for sig, fk in base_fks.items():
        if sig not in target_fks:
            items.append(
                _item("drop_foreign_key", SAFE, _fk_label(fk), "Dropping a foreign key relaxes a constraint — safe.")
            )

    items.sort(key=lambda i: (_SEVERITY_RANK.get(i["severity"], 9), i["target"]))

    summary = {
        "safe": sum(1 for i in items if i["severity"] == SAFE),
        "warning": sum(1 for i in items if i["severity"] == WARNING),
        "destructive": sum(1 for i in items if i["severity"] == DESTRUCTIVE),
        "total": len(items),
        "has_destructive": any(i["severity"] == DESTRUCTIVE for i in items),
        "has_blocking": any(i["severity"] in (WARNING, DESTRUCTIVE) for i in items),
    }
    return {"items": items, "summary": summary}
