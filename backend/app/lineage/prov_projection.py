"""Project a lineage graph into a W3C PROV-JSON document.

:func:`app.lineage.derive.build_lineage_graph` produces an internal DAG that
keeps derivation edges **by kind**. For an auditor or a downstream lineage
consumer, the interchange format that everyone already understands is W3C
PROV. This module is the pure projection from the internal graph to a
PROV-JSON dict:

* every snapshot id becomes a ``prov:Entity`` (qualified name ``pg:<id>``),
  including ids that appeared only as a dangling parent reference -- they
  are still referenced, so they still need an entity;
* every typed derivation edge becomes one ``wasDerivedFrom`` relation
  (blank-node key ``_:wdf<N>``) with ``prov:generatedEntity`` = the child,
  ``prov:usedEntity`` = the parent, and ``pg:derivationKind`` carrying the
  edge kind so the "by kind" information survives the projection.

PROV-JSON is plain JSON, so this needs no new dependency and the result is
directly ``json.dumps``-serializable. The projection is deterministic:
relations are numbered in ``(kind, child, parent)`` order.

References (APA 7th):

Moreau, L., & Missier, P. (Eds.). (2013). *PROV-DM: The PROV data model*
(W3C Recommendation). World Wide Web Consortium.
https://www.w3.org/TR/2013/REC-prov-dm-20130430/

Huynh, T. D., Jewell, M. O., Keshavarz, A. S., Michaelides, D. T., Yang,
H., & Moreau, L. (2013). *The PROV-JSON serialization* (W3C Member
Submission). World Wide Web Consortium.
https://www.w3.org/Submission/2013/SUBM-prov-json-20130424/
"""

from __future__ import annotations

from typing import Any

#: The PROV namespace IRI.
PROV_NAMESPACE = "http://www.w3.org/ns/prov#"

#: Default IRI prefix for pg-erd-cloud snapshot entities.
DEFAULT_BASE_URI = "urn:pg-erd-cloud:"


def prov_prefixes(base_uri: str = DEFAULT_BASE_URI) -> dict[str, str]:
    """Return the fixed PROV-JSON ``prefix`` map for a projection.

    ``pg`` is the pg-erd-cloud namespace (snapshot entities and the
    ``pg:derivationKind`` qualifier); ``prov`` is the W3C PROV namespace.
    """
    return {"pg": base_uri, "prov": PROV_NAMESPACE}


def _edge_triples(edges_by_kind: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Flatten ``{kind: [[parent, child], ...]}`` to sorted ``(kind, parent, child)``.

    The sort key is ``(kind, child, parent)`` so relation numbering is stable
    regardless of the input ordering.
    """
    triples: list[tuple[str, str, str]] = []
    for kind, pairs in (edges_by_kind or {}).items():
        for pair in pairs or ():
            parent, child = str(pair[0]), str(pair[1])
            triples.append((str(kind), parent, child))
    return sorted(triples, key=lambda t: (t[0], t[2], t[1]))


def to_prov_document(
    lineage_graph: dict[str, Any], *, base_uri: str = DEFAULT_BASE_URI
) -> dict[str, Any]:
    """Project a ``build_lineage_graph`` result into a PROV-JSON document.

    Args:
        lineage_graph: The dict returned by
            :func:`app.lineage.derive.build_lineage_graph` (only ``nodes`` and
            ``edges_by_kind`` are read; other keys are ignored). Missing keys
            are treated as empty.
        base_uri: The IRI the ``pg`` prefix expands to.

    Returns:
        A PROV-JSON dict with three top-level keys:

        ``prefix``
            The namespace map from :func:`prov_prefixes`.
        ``entity``
            ``{"pg:<snapshot_id>": {"prov:type": "pg:snapshot"}}`` for every
            id in ``nodes`` and every id referenced by an edge.
        ``wasDerivedFrom``
            ``{"_:wdf<N>": {"prov:generatedEntity": "pg:<child>",
            "prov:usedEntity": "pg:<parent>", "pg:derivationKind": "<kind>"}}``
            -- one entry per typed edge, numbered from 1 in
            ``(kind, child, parent)`` order.

        The result is deterministic and ``json.dumps``-serializable.
    """
    edges_by_kind = lineage_graph.get("edges_by_kind") or {}
    triples = _edge_triples(edges_by_kind)

    ids: set[str] = {str(n) for n in lineage_graph.get("nodes") or []}
    for _kind, parent, child in triples:
        ids.add(parent)
        ids.add(child)

    entity = {f"pg:{snapshot_id}": {"prov:type": "pg:snapshot"} for snapshot_id in sorted(ids)}

    was_derived_from: dict[str, dict[str, str]] = {}
    for index, (kind, parent, child) in enumerate(triples, start=1):
        was_derived_from[f"_:wdf{index}"] = {
            "prov:generatedEntity": f"pg:{child}",
            "prov:usedEntity": f"pg:{parent}",
            "pg:derivationKind": kind,
        }

    return {
        "prefix": prov_prefixes(base_uri),
        "entity": entity,
        "wasDerivedFrom": was_derived_from,
    }
