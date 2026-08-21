"""Check audit-column conventions (created_at / updated_at) across tables.

When most of a schema tracks row lifecycle with ``created_at``/``updated_at``
(or ``*_time``/``*_date`` variants), tables missing them are usually an
oversight — and the gap surfaces later as "when did this row change?" with no
answer. Like the naming lint, no convention is imposed: a table is only flagged
when the schema's *own* majority follows the convention.

Pure and dialect-agnostic.
"""

from __future__ import annotations

import re
from typing import Any

INFO = "info"

_CREATED = re.compile(r"^(created?_(at|on|time|date|dt)|create_(time|date|dt)|creation_date|reg(istered)?_(at|dt|date)|insert(ed)?_(at|dt))$")
_UPDATED = re.compile(r"^(updated?_(at|on|time|date|dt)|update_(time|date|dt)|modified?_(at|on|time|date|dt)|last_modified(_at)?|mod_dt)$")

# Only flag when at least this share of tables already follows the convention.
_ADOPTION_THRESHOLD = 0.5
_MIN_TABLES = 4


def check_audit_columns(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Flag tables missing the audit columns their schema-mates have."""
    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    columns = snapshot.get("columns") or []

    tables = {
        r.get("relation_oid"): r
        for r in relations
        if (r.get("relation_kind") or "r") in ("r", "p")
    }
    has_created: set[Any] = set()
    has_updated: set[Any] = set()
    for c in columns:
        oid = c.get("relation_oid")
        if oid not in tables:
            continue
        name = str(c.get("column_name") or "").lower()
        if _CREATED.match(name):
            has_created.add(oid)
        elif _UPDATED.match(name):
            has_updated.add(oid)

    total = len(tables)
    created_share = len(has_created) / total if total else 0.0
    updated_share = len(has_updated) / total if total else 0.0

    items: list[dict[str, Any]] = []
    if total >= _MIN_TABLES:
        for oid, rel in tables.items():
            qname = f"{rel.get('schema_name')}.{rel.get('relation_name')}"
            missing = []
            if created_share >= _ADOPTION_THRESHOLD and oid not in has_created:
                missing.append("created_at")
            if updated_share >= _ADOPTION_THRESHOLD and oid not in has_updated:
                missing.append("updated_at")
            if missing:
                items.append(
                    {
                        "category": "missing_audit_columns",
                        "severity": INFO,
                        "table": qname,
                        "missing": missing,
                        "detail": (
                            f"Missing {' & '.join(missing)} while most tables in this "
                            "schema track them — row lifecycle will be unanswerable."
                        ),
                    }
                )

    items.sort(key=lambda i: i["table"])
    summary = {
        "tables": total,
        "with_created": len(has_created),
        "with_updated": len(has_updated),
        "created_adoption": round(created_share, 2),
        "updated_adoption": round(updated_share, 2),
        "convention_active": total >= _MIN_TABLES
        and (created_share >= _ADOPTION_THRESHOLD or updated_share >= _ADOPTION_THRESHOLD),
        "total": len(items),
    }
    return {"items": items, "summary": summary}
