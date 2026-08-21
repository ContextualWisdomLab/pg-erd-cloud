"""Detect circular foreign-key dependencies in a snapshot.

A cycle in the FK graph (A → B → … → A) means there's no order in which the
tables can be created, dropped, or bulk-loaded without deferring constraints --
a real migration hazard. Self-references (``employee.manager_id → employee``)
are a normal, benign special case and are reported separately.

Pure and dialect-agnostic. Uses an iterative Tarjan SCC so a deep FK chain can't
blow the recursion limit.
"""

from __future__ import annotations

from typing import Any

WARNING = "warning"
INFO = "info"


def _sccs(nodes: list[str], adj: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan's strongly-connected components (iterative)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: list[list[str]] = []
    counter = 0

    for root in nodes:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(sorted(adj.get(root, set()))))]
        while work:
            v, it = work[-1]
            pushed = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack.add(w)
                    work.append((w, iter(sorted(adj.get(w, set())))))
                    pushed = True
                    break
                if w in on_stack:
                    low[v] = min(low[v], index[w])
            if pushed:
                continue
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                result.append(comp)
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
    return result


def detect_fk_cycles(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return circular-FK findings (multi-table cycles + self-references)."""
    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    fk_edges = snapshot.get("fk_edges") or []

    def _qname(oid: Any) -> str | None:
        rel = rel_by_oid.get(oid)
        if rel is None:
            return None
        return f"{rel.get('schema_name')}.{rel.get('relation_name')}"

    rel_by_oid = {r.get("relation_oid"): r for r in relations}

    adj: dict[str, set[str]] = {}
    nodes: set[str] = set()
    self_refs: set[str] = set()
    for edge in fk_edges:
        child = _qname(edge.get("child_relation_oid"))
        parent = _qname(edge.get("parent_relation_oid"))
        if child is None or parent is None:
            continue
        nodes.add(child)
        nodes.add(parent)
        if child == parent:
            self_refs.add(child)
        else:
            adj.setdefault(child, set()).add(parent)

    items: list[dict[str, Any]] = []
    for comp in _sccs(sorted(nodes), adj):
        if len(comp) >= 2:
            tables = sorted(comp)
            items.append(
                {
                    "category": "circular_dependency",
                    "severity": WARNING,
                    "tables": tables,
                    "detail": (
                        "Circular foreign-key dependency: "
                        + " → ".join(tables)
                        + " — no create/drop/load order works without deferring constraints."
                    ),
                }
            )
    for table in sorted(self_refs):
        items.append(
            {
                "category": "self_reference",
                "severity": INFO,
                "tables": [table],
                "detail": f"{table} references itself (hierarchical/tree) — usually fine; load roots first.",
            }
        )

    items.sort(key=lambda i: (0 if i["severity"] == WARNING else 1, i["tables"]))
    summary = {
        "circular_dependencies": sum(1 for i in items if i["category"] == "circular_dependency"),
        "self_references": len(self_refs),
        "total": len(items),
    }
    return {"items": items, "summary": summary}
