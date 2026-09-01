"""Tests for :mod:`app.lineage.prov_projection`.

The projection must emit a valid PROV-JSON skeleton, one entity per snapshot
id (dangling parents included), one ``wasDerivedFrom`` per typed edge with
its kind preserved, deterministic blank-node numbering, and JSON-serializable
output.
"""

from __future__ import annotations

import json

from app.lineage.derive import DERIVATION_KINDS, build_lineage_graph
from app.lineage.prov_projection import (
    PROV_NAMESPACE,
    prov_prefixes,
    to_prov_document,
)


def _derivation(parent: str, child: str, kind: str) -> dict[str, str]:
    return {
        "parent_snapshot_id": parent,
        "child_snapshot_id": child,
        "derivation_kind": kind,
    }


def test_empty_graph_has_prefix_but_no_entities_or_relations() -> None:
    doc = to_prov_document(build_lineage_graph([], []))
    assert doc["prefix"] == prov_prefixes()
    assert doc["prefix"]["prov"] == PROV_NAMESPACE
    assert doc["entity"] == {}
    assert doc["wasDerivedFrom"] == {}


def test_single_node_yields_one_entity_no_derivation() -> None:
    doc = to_prov_document(build_lineage_graph(["snap_one"], []))
    assert doc["entity"] == {"pg:snap_one": {"prov:type": "pg:snapshot"}}
    assert doc["wasDerivedFrom"] == {}


def test_linear_chain_has_two_derivations_numbered_deterministically() -> None:
    graph = build_lineage_graph(
        ["snap_a", "snap_b", "snap_c"],
        [
            _derivation("snap_a", "snap_b", "captured_from"),
            _derivation("snap_b", "snap_c", "normalized_from"),
        ],
    )
    doc = to_prov_document(graph)
    assert set(doc["entity"]) == {"pg:snap_a", "pg:snap_b", "pg:snap_c"}
    wdf = doc["wasDerivedFrom"]
    assert list(wdf) == ["_:wdf1", "_:wdf2"]
    # Sort key is (kind, child, parent): captured_from < normalized_from.
    assert wdf["_:wdf1"] == {
        "prov:generatedEntity": "pg:snap_b",
        "prov:usedEntity": "pg:snap_a",
        "pg:derivationKind": "captured_from",
    }
    assert wdf["_:wdf2"]["pg:derivationKind"] == "normalized_from"


def test_diamond_keeps_all_four_edges() -> None:
    graph = build_lineage_graph(
        ["root", "left", "right", "merged"],
        [
            _derivation("root", "left", "captured_from"),
            _derivation("root", "right", "captured_from"),
            _derivation("left", "merged", "compared_with"),
            _derivation("right", "merged", "compared_with"),
        ],
    )
    doc = to_prov_document(graph)
    assert len(doc["wasDerivedFrom"]) == 4
    pairs = {
        (v["prov:usedEntity"], v["prov:generatedEntity"])
        for v in doc["wasDerivedFrom"].values()
    }
    assert pairs == {
        ("pg:root", "pg:left"),
        ("pg:root", "pg:right"),
        ("pg:left", "pg:merged"),
        ("pg:right", "pg:merged"),
    }


def test_every_derivation_kind_appears_in_the_projection() -> None:
    parents = [f"p_{i}" for i in range(len(DERIVATION_KINDS))]
    children = [f"c_{i}" for i in range(len(DERIVATION_KINDS))]
    derivations = [
        _derivation(parents[i], children[i], kind)
        for i, kind in enumerate(DERIVATION_KINDS)
    ]
    graph = build_lineage_graph(parents + children, derivations)
    doc = to_prov_document(graph)
    seen = {v["pg:derivationKind"] for v in doc["wasDerivedFrom"].values()}
    assert seen == set(DERIVATION_KINDS)


def test_dangling_parent_reference_still_gets_an_entity() -> None:
    # "ghost" is never declared as a node, only referenced as a parent.
    graph = build_lineage_graph(
        ["known_child"],
        [_derivation("ghost", "known_child", "imported_from")],
    )
    assert "ghost" in graph["dangling_references"]
    doc = to_prov_document(graph)
    assert "pg:ghost" in doc["entity"]
    assert doc["wasDerivedFrom"]["_:wdf1"]["prov:usedEntity"] == "pg:ghost"


def test_custom_base_uri_flows_into_the_prefix_map() -> None:
    doc = to_prov_document(
        build_lineage_graph(["s1"], []), base_uri="https://lineage.example/"
    )
    assert doc["prefix"]["pg"] == "https://lineage.example/"


def test_output_is_json_serializable_and_round_trips() -> None:
    graph = build_lineage_graph(
        ["a", "b"], [_derivation("a", "b", "exported_from")]
    )
    doc = to_prov_document(graph)
    assert json.loads(json.dumps(doc)) == doc


def test_projection_is_deterministic() -> None:
    graph = build_lineage_graph(
        ["a", "b", "c"],
        [
            _derivation("a", "b", "planned_from"),
            _derivation("a", "c", "captured_from"),
        ],
    )
    assert to_prov_document(graph) == to_prov_document(graph)


def test_missing_keys_are_treated_as_empty() -> None:
    doc = to_prov_document({})
    assert doc["entity"] == {}
    assert doc["wasDerivedFrom"] == {}
    assert "prefix" in doc
