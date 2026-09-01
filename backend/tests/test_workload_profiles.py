"""Tests for :mod:`app.perf.workload_profiles`.

The named profiles must hit the exact object counts from issue #951, be
byte-for-byte deterministic under a fixed seed, and never leak a real name or
an invented performance threshold.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.perf.workload_profiles import (
    PROFILE_SPECS,
    deep_dependency_chain_snapshot,
    dense_fk_cluster_snapshot,
    disconnected_components_snapshot,
    generate_workload_snapshot,
    list_profiles,
    multilingual_identifier_snapshot,
    partition_hierarchy_snapshot,
    wide_relation_snapshot,
)

# (schemas, relations, columns, fk_edges, indexes, snapshots/project) per #951.
_EXPECTED = {
    "small": (5, 100, 2_000, 200, 300, 20),
    "medium": (25, 1_000, 25_000, 3_000, 5_000, 100),
    "large": (100, 10_000, 250_000, 30_000, 50_000, 500),
}

_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


def test_profile_specs_match_the_issue_table_exactly() -> None:
    assert list_profiles() == ["small", "medium", "large"]
    for name, (sch, rel, col, fk, idx, snaps) in _EXPECTED.items():
        spec = PROFILE_SPECS[name]
        assert (spec.schemas, spec.relations, spec.columns) == (sch, rel, col)
        assert (spec.fk_edges, spec.indexes, spec.snapshots_per_project) == (fk, idx, snaps)


@pytest.mark.parametrize("profile", ["small", "medium"])
def test_generated_snapshot_hits_the_profile_counts(profile: str) -> None:
    sch, rel, col, fk, idx, _ = _EXPECTED[profile]
    snap = generate_workload_snapshot(profile)
    assert len(snap["schemas"]) == sch
    assert len(snap["relations"]) == rel
    assert len(snap["columns"]) == col
    assert len(snap["fk_edges"]) == fk
    assert len(snap["indexes"]) == idx
    # Every relation has a primary key + PK constraint.
    assert len(snap["pk_columns"]) == rel
    assert sum(1 for c in snap["constraints"] if c["constraint_type"] == "p") == rel


def test_output_is_byte_for_byte_deterministic() -> None:
    a = generate_workload_snapshot("small")
    b = generate_workload_snapshot("small", seed=PROFILE_SPECS["small"].default_seed)
    assert a == b
    # A different seed changes the content but not the counts.
    c = generate_workload_snapshot("small", seed=1)
    assert c != a
    assert len(c["relations"]) == len(a["relations"])
    assert len(c["columns"]) == len(a["columns"])


def test_named_profile_identifiers_are_two_word_snake_case() -> None:
    snap = generate_workload_snapshot("small")
    for relation in snap["relations"]:
        name = relation["relation_name"]
        assert _SNAKE.match(name) and name.count("_") >= 2, name
    for column in snap["columns"]:
        name = column["column_name"]
        assert _SNAKE.match(name) and "_" in name, name
    for index in snap["indexes"]:
        assert _SNAKE.match(index["index_name"]), index["index_name"]


def test_foreign_keys_reference_real_relations_and_columns() -> None:
    snap = generate_workload_snapshot("small")
    oids = {r["relation_oid"] for r in snap["relations"]}
    columns_by_oid: dict[int, set[str]] = {}
    for column in snap["columns"]:
        columns_by_oid.setdefault(column["relation_oid"], set()).add(column["column_name"])
    for edge in snap["fk_edges"]:
        assert edge["child_relation_oid"] in oids
        assert edge["parent_relation_oid"] in oids
        assert edge["child_relation_oid"] != edge["parent_relation_oid"]
        assert edge["child_column_name"] in columns_by_oid[edge["child_relation_oid"]]


def test_wide_relation_case_has_one_relation_and_the_requested_columns() -> None:
    snap = wide_relation_snapshot(column_count=5_000)
    assert len(snap["relations"]) == 1
    assert len(snap["columns"]) == 5_000
    assert wide_relation_snapshot() == wide_relation_snapshot()


def test_deep_chain_case_is_a_linear_fk_chain() -> None:
    snap = deep_dependency_chain_snapshot(depth=50)
    assert len(snap["relations"]) == 50
    assert len(snap["fk_edges"]) == 49
    for edge in snap["fk_edges"]:
        assert edge["parent_relation_oid"] == edge["child_relation_oid"] - 1


def test_dense_fk_cluster_and_disconnected_components_shapes() -> None:
    dense = dense_fk_cluster_snapshot(relation_count=10)
    assert len(dense["relations"]) == 10
    assert len(dense["fk_edges"]) == 10 * 9  # near-complete directed graph

    disc = disconnected_components_snapshot(component_count=4, per_component=5)
    assert len(disc["relations"]) == 20
    # No FK edge crosses a component boundary.
    for edge in disc["fk_edges"]:
        assert (edge["child_relation_oid"] - 1) // 5 == (edge["parent_relation_oid"] - 1) // 5


def test_multilingual_and_partition_cases() -> None:
    ml = multilingual_identifier_snapshot()
    assert any(not r["relation_name"].isascii() for r in ml["relations"])
    assert any(len(r.get("relation_comment") or "") > 1_000 for r in ml["relations"])

    ph = partition_hierarchy_snapshot(child_count=12)
    assert ph["relations"][0]["partition_key"] == "RANGE (recorded_at)"
    assert sum(1 for r in ph["relations"] if r.get("is_partition")) == 12
    assert partition_hierarchy_snapshot() == partition_hierarchy_snapshot()


def test_module_states_thresholds_come_from_measurement_and_invents_none() -> None:
    text = Path("app/perf/workload_profiles.py").read_text(encoding="utf-8")
    lowered = text.lower()
    # The module must say, in words, that targets are measured not invented.
    assert "set from measured baseline runs" in lowered
    assert "never invented" in lowered
    # And it must not carry a concrete latency/percentile threshold value.
    assert re.search(r"\b\d+(\.\d+)?\s*(ms|milliseconds|seconds)\b", lowered) is None
    assert re.search(r"p9[59]\s*[<>=:]", lowered) is None
    assert re.search(r"\b\d+\s*(rps|qps|req/s|requests per second)\b", lowered) is None
