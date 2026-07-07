"""Flag unusually wide tables (denormalization / god-table smell).

A table with dozens of columns is often a denormalized dumping ground or a
"god table" that has accreted responsibilities -- hard to index, slow to scan,
and a magnet for NULLs. This flags tables whose column count crosses configurable
thresholds so a reviewer can consider splitting them.

Pure and dialect-agnostic. Thresholds are advisory, not law -- some wide tables
(analytics fact tables) are legitimately wide; ponytail: absolute count only.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

WARNING = "warning"
INFO = "info"


def detect_wide_tables(
    snapshot: dict[str, Any] | None,
    warn_threshold: int = 40,
    info_threshold: int = 25,
) -> dict[str, Any]:
    """Return tables exceeding the column-count thresholds, widest first."""
    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    columns = snapshot.get("columns") or []

    # Only ordinary/partitioned tables count (views legitimately project many cols).
    table_oids = {
        r.get("relation_oid"): r
        for r in relations
        if (r.get("relation_kind") or "r") in ("r", "p")
    }
    counts: Counter[Any] = Counter()
    for c in columns:
        oid = c.get("relation_oid")
        if oid in table_oids:
            counts[oid] += 1

    items: list[dict[str, Any]] = []
    for oid, n in counts.items():
        if n > warn_threshold:
            severity = WARNING
        elif n > info_threshold:
            severity = INFO
        else:
            continue
        rel = table_oids[oid]
        items.append(
            {
                "table": f"{rel.get('schema_name')}.{rel.get('relation_name')}",
                "columns": n,
                "severity": severity,
                "detail": (
                    f"{n} columns (> {warn_threshold if severity == WARNING else info_threshold}) "
                    "— consider splitting or normalizing."
                ),
            }
        )

    items.sort(key=lambda i: (-i["columns"], i["table"]))
    summary = {
        "warning": sum(1 for i in items if i["severity"] == WARNING),
        "info": sum(1 for i in items if i["severity"] == INFO),
        "total": len(items),
        "warn_threshold": warn_threshold,
        "info_threshold": info_threshold,
    }
    return {"items": items, "summary": summary}
