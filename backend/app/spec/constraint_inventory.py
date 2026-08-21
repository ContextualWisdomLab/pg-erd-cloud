"""Inventory business rules living in constraints, and flag CASCADE risk.

Reverse engineering isn't just tables and columns -- the *business rules* often
hide in CHECK constraints, and the operational hazards hide in FK referential
actions. This inventories both:

* **check_rules** -- every CHECK constraint with its expression: the closest
  thing a legacy database has to documented invariants.
* **cascade_deletes** (warning) -- ``ON DELETE CASCADE`` foreign keys: deleting
  a parent silently deletes children; every operator should know these paths.
* **set_null_deletes** (info) -- ``ON DELETE SET NULL``: orphaned-but-kept rows.

Pure and dialect-agnostic (PostgreSQL action codes 'c'/'n' plus spelled-out
variants are both handled).
"""

from __future__ import annotations

from typing import Any

WARNING = "warning"
INFO = "info"

_CASCADE = {"c", "cascade"}
_SET_NULL = {"n", "set null", "set_null"}


def build_constraint_inventory(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return CHECK-rule inventory and FK delete-action risk findings."""
    snapshot = snapshot or {}
    constraints = snapshot.get("constraints") or []

    check_rules: list[dict[str, Any]] = []
    cascade_items: list[dict[str, Any]] = []

    for con in constraints:
        ctype = str(con.get("constraint_type") or "").lower()
        table = f"{con.get('schema_name')}.{con.get('relation_name')}"
        name = str(con.get("constraint_name") or "")

        if ctype == "c":
            expr = con.get("check_expr") or con.get("constraint_def")
            check_rules.append(
                {
                    "table": table,
                    "constraint": name,
                    "expression": str(expr or ""),
                }
            )
        elif ctype == "f":
            on_delete = str(con.get("fk_on_delete") or "").lower()
            target = (
                f"{con.get('foreign_schema_name')}.{con.get('foreign_relation_name')}"
            )
            if on_delete in _CASCADE:
                cascade_items.append(
                    {
                        "category": "cascade_delete",
                        "severity": WARNING,
                        "table": table,
                        "constraint": name,
                        "references": target,
                        "detail": (
                            f"Deleting a row in {target} silently deletes rows in "
                            f"{table} (ON DELETE CASCADE via '{name}')."
                        ),
                    }
                )
            elif on_delete in _SET_NULL:
                cascade_items.append(
                    {
                        "category": "set_null_delete",
                        "severity": INFO,
                        "table": table,
                        "constraint": name,
                        "references": target,
                        "detail": (
                            f"Deleting a row in {target} nulls the reference in "
                            f"{table} (ON DELETE SET NULL via '{name}') — rows are kept but orphaned."
                        ),
                    }
                )

    check_rules.sort(key=lambda r: (r["table"], r["constraint"]))
    cascade_items.sort(
        key=lambda i: (0 if i["severity"] == WARNING else 1, i["table"], i["constraint"])
    )

    summary = {
        "check_rules": len(check_rules),
        "cascade_deletes": sum(1 for i in cascade_items if i["category"] == "cascade_delete"),
        "set_null_deletes": sum(1 for i in cascade_items if i["category"] == "set_null_delete"),
    }
    return {"check_rules": check_rules, "delete_actions": cascade_items, "summary": summary}
