"""Detect redundant (prefix-shadowed) and duplicate indexes.

Every index costs write amplification and storage on each INSERT/UPDATE. An
index on ``(a)`` is *redundant* when another index on the same table starts
with ``(a, ...)`` -- the wider index already serves those scans. Two indexes
over the identical column list are *duplicates*. Both are safe wins to drop.

Pure and dialect-agnostic. Column lists come from a best-effort parse of
``index_def``; expression/partial indexes that don't parse are skipped rather
than guessed (ponytail: false negatives over false positives -- dropping an
index is cheap to re-do, a wrong "drop this" suggestion is not).
"""

from __future__ import annotations

import re
from typing import Any

WARNING = "warning"
INFO = "info"


def _index_columns(index_def: object) -> list[str]:
    """Best-effort ordered column list from an index definition."""
    text = str(index_def or "")
    if " where " in text.lower():
        return []  # partial index: not comparable
    match = re.search(r"\(([^()]*)\)", text)
    if not match:
        return []
    cols: list[str] = []
    for part in match.group(1).split(","):
        token = part.strip().strip('"').split()
        if not token or "(" in part:
            return []  # expression index: not comparable
        cols.append(token[0].strip('"').lower())
    return cols


def detect_index_redundancy(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return duplicate and prefix-shadowed indexes, per table."""
    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    indexes = snapshot.get("indexes") or []
    rel_by_oid = {r.get("relation_oid"): r for r in relations}

    by_table: dict[Any, list[tuple[str, tuple[str, ...], bool]]] = {}
    for idx in indexes:
        oid = idx.get("relation_oid") or idx.get("table_oid")
        cols = tuple(_index_columns(idx.get("index_def")))
        if not cols:
            continue
        name = str(idx.get("index_name") or "")
        unique = bool(idx.get("is_unique") or idx.get("is_primary"))
        by_table.setdefault(oid, []).append((name, cols, unique))

    items: list[dict[str, Any]] = []
    for oid, idx_list in by_table.items():
        rel = rel_by_oid.get(oid) or {}
        table = f"{rel.get('schema_name')}.{rel.get('relation_name')}"
        for i, (name_a, cols_a, unique_a) in enumerate(idx_list):
            for name_b, cols_b, unique_b in idx_list[i + 1:]:
                if cols_a == cols_b:
                    # exact duplicate: suggest dropping the non-unique one
                    drop = name_b if unique_a and not unique_b else name_a if unique_b and not unique_a else name_b
                    items.append(
                        {
                            "category": "duplicate_index", "severity": WARNING,
                            "table": table, "index": drop,
                            "kept": name_a if drop == name_b else name_b,
                            "columns": list(cols_a),
                            "detail": f"'{drop}' duplicates '{name_a if drop == name_b else name_b}' on ({', '.join(cols_a)}) — drop it.",
                        }
                    )
                    continue
                for shorter, longer, s_name, l_name, s_unique in (
                    (cols_a, cols_b, name_a, name_b, unique_a),
                    (cols_b, cols_a, name_b, name_a, unique_b),
                ):
                    if longer[: len(shorter)] == shorter:
                        if s_unique:
                            break  # unique index enforces a constraint; never suggest dropping
                        items.append(
                            {
                                "category": "prefix_redundant_index", "severity": INFO,
                                "table": table, "index": s_name,
                                "kept": l_name,
                                "columns": list(shorter),
                                "detail": f"'{s_name}' on ({', '.join(shorter)}) is a prefix of '{l_name}' on ({', '.join(longer)}) — likely droppable.",
                            }
                        )
                        break

    items.sort(key=lambda i: (0 if i["severity"] == WARNING else 1, i["table"], i["index"]))
    summary = {
        "duplicates": sum(1 for i in items if i["category"] == "duplicate_index"),
        "prefix_redundant": sum(1 for i in items if i["category"] == "prefix_redundant_index"),
        "total": len(items),
    }
    return {"items": items, "summary": summary}
