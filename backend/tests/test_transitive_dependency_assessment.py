"""Tests for :mod:`app.spec.transitive_dependency_assessment`.

The analyzer must stay silent without evidence, raise a confirmed 3NF
finding only from a declared functional dependency that genuinely violates
3NF, flag the catalog-only structural precondition as ``inferred`` with a
caveat, honour waivers, and be deterministic.
"""

from __future__ import annotations

from typing import Any

from app.spec.transitive_dependency_assessment import (
    ASSESSMENT_VERSION,
    FINDING_KINDS,
    assess_transitive_dependencies,
)


def _snapshot(
    columns: list[str],
    *,
    not_null: set[str] | None = None,
    pk: list[str] | None = None,
    uniques: list[list[str]] | None = None,
    fks: list[str] | None = None,
    relation_kind: str = "r",
) -> dict[str, Any]:
    """Build a one-relation snapshot ``public.thing`` with the given columns."""
    not_null = not_null or set()
    oid = 1
    rows_columns = [
        {
            "relation_oid": oid,
            "column_position": i + 1,
            "column_name": name,
            "is_not_null": name in not_null,
            "data_type": "text",
            "type_category": "S",
            "array_dimensions": 0,
        }
        for i, name in enumerate(columns)
    ]
    pos = {name: i + 1 for i, name in enumerate(columns)}
    constraints = []
    for j, cols in enumerate(uniques or []):
        constraints.append(
            {
                "relation_oid": oid,
                "constraint_type": "u",
                "constraint_name": f"uq_{j}",
                "constrained_attnums": [pos[c] for c in cols],
            }
        )
    return {
        "relations": [
            {
                "relation_oid": oid,
                "schema_name": "public",
                "relation_name": "thing",
                "relation_kind": relation_kind,
            }
        ],
        "columns": rows_columns,
        "pk_columns": [
            {"relation_oid": oid, "column_name": c, "column_ordinal": k + 1}
            for k, c in enumerate(pk or [])
        ],
        "constraints": constraints,
        "fk_edges": [
            {
                "child_relation_oid": oid,
                "parent_relation_oid": 99,
                "child_column_name": c,
                "parent_column_name": "id",
            }
            for c in (fks or [])
        ],
    }


def _kinds(report: dict[str, Any]) -> list[str]:
    return [f["kind"] for f in report["findings"]]


def test_empty_snapshot_is_clean() -> None:
    report = assess_transitive_dependencies(None)
    assert report["version"] == ASSESSMENT_VERSION
    assert report["evidence_basis"] == "catalog_and_declared"
    assert report["findings"] == []
    assert report["relation_assessments"] == []
    assert report["unresolved_declared_fds"] == []


def test_clean_3nf_schema_has_no_findings() -> None:
    snap = _snapshot(["id", "label"], not_null={"id"}, pk=["id"])
    report = assess_transitive_dependencies(snap)
    assert report["findings"] == []
    assert report["relation_assessments"][0]["candidate_keys"] == [["id"]]


def test_declared_transitive_dependency_is_flagged() -> None:
    snap = _snapshot(
        ["id", "zip_code", "city"], not_null={"id"}, pk=["id"]
    )
    fds = [
        {"relation": "public.thing", "determinant": ["zip_code"], "dependent": ["city"]}
    ]
    report = assess_transitive_dependencies(
        snap, declared_functional_dependencies=fds
    )
    kinds = _kinds(report)
    assert "transitive_dependency_via_declared_fd" in kinds
    assert "candidate_3nf_split" in kinds
    tdep = next(
        f for f in report["findings"]
        if f["kind"] == "transitive_dependency_via_declared_fd"
    )
    assert tdep["evidence_class"] == "declared"
    assert tdep["normal_form_scope"] == "3NF"
    assert tdep["confidence"] == "high"
    assert report["relation_assessments"][0]["declared_fd_count"] == 1


def test_declared_fd_on_a_superkey_determinant_is_not_a_violation() -> None:
    snap = _snapshot(["id", "city"], not_null={"id"}, pk=["id"])
    fds = [
        {"relation": "public.thing", "determinant": ["id"], "dependent": ["city"]}
    ]
    report = assess_transitive_dependencies(
        snap, declared_functional_dependencies=fds
    )
    assert _kinds(report) == []


def test_declared_fd_with_prime_dependent_is_not_a_violation() -> None:
    # Composite key (a, b); a -> b would make b depend on a non-superkey, but
    # b is a prime attribute, which 3NF permits.
    snap = _snapshot(
        ["a", "b", "note"], not_null={"a", "b"}, pk=["a", "b"]
    )
    fds = [{"relation": "public.thing", "determinant": ["a"], "dependent": ["b"]}]
    report = assess_transitive_dependencies(
        snap, declared_functional_dependencies=fds
    )
    assert "transitive_dependency_via_declared_fd" not in _kinds(report)


def test_non_null_unique_counts_as_a_candidate_key() -> None:
    snap = _snapshot(
        ["pk", "email", "city"],
        not_null={"pk", "email"},
        pk=["pk"],
        uniques=[["email"]],
    )
    fds = [
        {"relation": "public.thing", "determinant": ["email"], "dependent": ["city"]}
    ]
    report = assess_transitive_dependencies(
        snap, declared_functional_dependencies=fds
    )
    # email is a candidate key, so email -> city is a key dependency, not a
    # transitive one.
    assert "transitive_dependency_via_declared_fd" not in _kinds(report)


def test_non_key_reference_cluster_is_inferred_with_a_caveat() -> None:
    snap = _snapshot(
        ["id", "order_ref", "product_ref", "descriptive_note"],
        not_null={"id"},
        pk=["id"],
        fks=["order_ref", "product_ref"],
    )
    report = assess_transitive_dependencies(snap)
    cluster = next(
        f for f in report["findings"] if f["kind"] == "non_key_reference_cluster"
    )
    assert cluster["evidence_class"] == "inferred"
    assert cluster["confidence"] == "low"
    assert "profiling" in cluster["false_positive_caveat"].lower()


def test_single_foreign_key_is_not_a_cluster() -> None:
    snap = _snapshot(
        ["id", "order_ref", "note"], not_null={"id"}, pk=["id"], fks=["order_ref"]
    )
    report = assess_transitive_dependencies(snap)
    assert "non_key_reference_cluster" not in _kinds(report)


def test_fk_cluster_that_is_the_primary_key_is_not_flagged() -> None:
    snap = _snapshot(
        ["order_ref", "product_ref"],
        not_null={"order_ref", "product_ref"},
        pk=["order_ref", "product_ref"],
        fks=["order_ref", "product_ref"],
    )
    report = assess_transitive_dependencies(snap)
    assert "non_key_reference_cluster" not in _kinds(report)


def test_waiver_flips_a_finding_to_waived() -> None:
    snap = _snapshot(["id", "zip_code", "city"], not_null={"id"}, pk=["id"])
    fds = [
        {"relation": "public.thing", "determinant": ["zip_code"], "dependent": ["city"]}
    ]
    waivers = [
        {
            "scope": {"relation": "thing", "kind": "transitive_dependency_via_declared_fd"},
            "owner": "data-platform",
            "reason": "denormalized on purpose for the reporting read model",
            "review_date": "2026-09-01",
            "expiry": "2027-01-01",
        }
    ]
    report = assess_transitive_dependencies(
        snap, declared_functional_dependencies=fds, waivers=waivers
    )
    tdep = next(
        f for f in report["findings"]
        if f["kind"] == "transitive_dependency_via_declared_fd"
    )
    assert tdep["evidence_class"] == "waived"
    assert tdep["waiver"]["owner"] == "data-platform"


def test_unresolved_declared_fds_are_reported_not_dropped() -> None:
    snap = _snapshot(["id", "city"], not_null={"id"}, pk=["id"])
    fds = [
        {"relation": "public.missing", "determinant": ["a"], "dependent": ["b"]},
        {"relation": "public.thing", "determinant": ["nope"], "dependent": ["city"]},
        {"relation": "public.thing", "determinant": [], "dependent": ["city"]},
    ]
    report = assess_transitive_dependencies(
        snap, declared_functional_dependencies=fds
    )
    reasons = sorted(u["reason"] for u in report["unresolved_declared_fds"])
    assert reasons == [
        "empty_determinant_or_dependent",
        "relation_not_found",
        "unknown_columns:nope",
    ]
    assert report["findings"] == []


def test_output_is_deterministic() -> None:
    snap = _snapshot(
        ["id", "zip_code", "city", "order_ref", "product_ref", "descriptive_note"],
        not_null={"id"},
        pk=["id"],
        fks=["order_ref", "product_ref"],
    )
    fds = [
        {"relation": "public.thing", "determinant": ["zip_code"], "dependent": ["city"]}
    ]
    a = assess_transitive_dependencies(snap, declared_functional_dependencies=fds)
    b = assess_transitive_dependencies(snap, declared_functional_dependencies=fds)
    assert a == b
    assert set(_kinds(a)).issubset(set(FINDING_KINDS))


def test_declared_fds_none_still_returns_catalog_findings() -> None:
    snap = _snapshot(
        ["id", "order_ref", "product_ref", "note"],
        not_null={"id"},
        pk=["id"],
        fks=["order_ref", "product_ref"],
    )
    report = assess_transitive_dependencies(snap, declared_functional_dependencies=None)
    assert _kinds(report) == ["non_key_reference_cluster"]
