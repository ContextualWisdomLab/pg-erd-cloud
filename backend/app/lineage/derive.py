"""Build a typed lineage DAG from snapshot and derivation records.

Pure: no I/O, no database. Given the snapshot ids and the typed
:class:`~app.lineage.lineage_model.SnapshotDerivation` edges, produce a graph
with edges kept **by kind** (never collapsed to a generic "derived from"),
detect cycles, list orphans, and return a topological order.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable

from app.lineage.lineage_model import DerivationKind

#: The accepted derivation edge kinds (runtime copy of the ``Literal``).
DERIVATION_KINDS: tuple[DerivationKind, ...] = (
    "captured_from",
    "imported_from",
    "normalized_from",
    "compared_with",
    "exported_from",
    "planned_from",
)


class LineageCycleError(ValueError):
    """Raised when the derivation edges contain a cycle (lineage must be a DAG)."""

    def __init__(self, involved: Iterable[str]) -> None:
        """Record the snapshot ids that remained in the cycle."""

        self.involved = sorted(involved)
        super().__init__(
            "derivation edges form a cycle involving: " + ", ".join(self.involved)
        )


def build_lineage_graph(
    snapshot_ids: Iterable[str],
    derivations: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the lineage DAG.

    Args:
        snapshot_ids: All known snapshot ids (nodes). Ids referenced by an edge
            but absent here are reported under ``dangling_references`` rather
            than silently added.
        derivations: Iterable of ``SnapshotDerivation``-shaped dicts.

    Returns:
        A dict with:

        ``nodes``: sorted list of snapshot ids.
        ``edges_by_kind``: ``{derivation_kind: [[parent, child], ...]}`` for
            every kind present.
        ``adjacency``: ``{parent: [child, ...]}`` (kind-agnostic, for traversal).
        ``topological_order``: ids ordered so every parent precedes its child.
        ``roots`` / ``leaves``: ids with no incoming / no outgoing edge.
        ``orphans``: ids with neither incoming nor outgoing edges.
        ``dangling_references``: edge endpoints not present in ``snapshot_ids``.

    Raises:
        ValueError: If an edge has an unknown ``derivation_kind`` or is a
            self-loop.
        LineageCycleError: If the edges contain a cycle.
    """

    nodes = set(snapshot_ids)
    edges_by_kind: dict[str, list[list[str]]] = {}
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    indegree: dict[str, int] = {node: 0 for node in nodes}
    dangling: set[str] = set()

    for edge in derivations:
        parent = str(edge["parent_snapshot_id"])
        child = str(edge["child_snapshot_id"])
        kind = str(edge["derivation_kind"])
        if kind not in DERIVATION_KINDS:
            raise ValueError(f"unknown derivation_kind: {kind!r}")
        if parent == child:
            raise ValueError(f"derivation edge is a self-loop on {parent!r}")
        for endpoint in (parent, child):
            if endpoint not in nodes:
                dangling.add(endpoint)
                nodes.add(endpoint)
                adjacency.setdefault(endpoint, set())
                indegree.setdefault(endpoint, 0)
        edges_by_kind.setdefault(kind, [])
        if [parent, child] not in edges_by_kind[kind]:
            edges_by_kind[kind].append([parent, child])
        if child not in adjacency[parent]:
            adjacency[parent].add(child)
            indegree[child] += 1

    # Kahn's algorithm for the topological order + cycle detection.
    queue: deque[str] = deque(sorted(n for n in nodes if indegree[n] == 0))
    order: list[str] = []
    local_indegree = dict(indegree)
    while queue:
        current = queue.popleft()
        order.append(current)
        for nxt in sorted(adjacency[current]):
            local_indegree[nxt] -= 1
            if local_indegree[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(nodes):
        involved = {n for n in nodes if local_indegree[n] > 0}
        raise LineageCycleError(involved)

    roots = sorted(n for n in nodes if indegree[n] == 0)
    leaves = sorted(n for n in nodes if not adjacency[n])
    orphans = sorted(
        n for n in nodes if indegree[n] == 0 and not adjacency[n]
    )

    return {
        "nodes": sorted(nodes),
        "edges_by_kind": {k: edges_by_kind[k] for k in sorted(edges_by_kind)},
        "adjacency": {k: sorted(v) for k, v in sorted(adjacency.items())},
        "topological_order": order,
        "roots": roots,
        "leaves": leaves,
        "orphans": orphans,
        "dangling_references": sorted(dangling),
    }
