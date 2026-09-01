"""Tests for :mod:`app.spec.normalization_report` (the report envelope)."""

from __future__ import annotations

from typing import Any

from app.spec.normalization_report import (
    REPORT_VERSION,
    build_normalization_report,
    schema_fingerprint,
)

_CLEAN_SNAPSHOT: dict[str, Any] = {
    "relations": [
        {"relation_oid": 1, "schema_name": "public", "relation_name": "app_user", "relation_kind": "r"}
    ],
    "columns": [
        {"relation_oid": 1, "column_position": 1, "column_name": "user_id", "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 1, "column_position": 2, "column_name": "email_address", "data_type": "text", "is_not_null": True},
    ],
    "pk_columns": [{"relation_oid": 1, "column_name": "user_id"}],
}

_JSONB_SNAPSHOT: dict[str, Any] = {
    "relations": [
        {"relation_oid": 1, "schema_name": "public", "relation_name": "schema_snapshot_data", "relation_kind": "r"}
    ],
    "columns": [
        {"relation_oid": 1, "column_position": 1, "column_name": "snapshot_id", "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 1, "column_position": 2, "column_name": "snapshot_json", "data_type": "jsonb", "is_not_null": True},
    ],
    "pk_columns": [{"relation_oid": 1, "column_name": "snapshot_id"}],
}


def test_envelope_wraps_the_analyzer_output_additively() -> None:
    report = build_normalization_report(_CLEAN_SNAPSHOT)
    assert report["report_version"] == REPORT_VERSION
    assert report["schema_fingerprint"].startswith("sha256:")
    assert "generated_at" in report
    # Analyzer keys are preserved.
    assert report["version"] == "1"
    assert report["evidence_basis"] == "catalog_only"
    assert isinstance(report["findings"], list)
    assert isinstance(report["relation_assessments"], list)


def test_fingerprint_is_dict_key_order_independent_and_distinguishing() -> None:
    # Same content, different dict-key insertion order -> same fingerprint
    # (the introspector emits list rows in a deterministic SQL order, so only
    # dict-key order needs to be canonicalized).
    reordered = {
        "pk_columns": _CLEAN_SNAPSHOT["pk_columns"],
        "relations": _CLEAN_SNAPSHOT["relations"],
        "columns": _CLEAN_SNAPSHOT["columns"],
    }
    assert schema_fingerprint(_CLEAN_SNAPSHOT) == schema_fingerprint(reordered)
    assert schema_fingerprint(None) == schema_fingerprint({})
    assert schema_fingerprint(_CLEAN_SNAPSHOT) != schema_fingerprint(_JSONB_SNAPSHOT)


def test_summary_headline_for_a_clean_schema() -> None:
    summary = build_normalization_report(_CLEAN_SNAPSHOT)["summary"]
    assert summary["relations_assessed"] == 1
    assert summary["relations_needing_review"] == 0
    assert summary["relations_by_normal_form"] == {"bcnf": 1}
    assert "BCNF" in summary["headline"]


def test_summary_counts_findings_and_review_relations() -> None:
    summary = build_normalization_report(_JSONB_SNAPSHOT)["summary"]
    assert summary["relations_needing_review"] == 1
    assert summary["relations_by_normal_form"] == {"1nf_review": 1}
    assert summary["findings_by_evidence_class"].get("observed") == 1
    assert "review" in summary["headline"]


def test_summary_reflects_waivers() -> None:
    waivers = [
        {
            "scope": {"relation": "schema_snapshot_data", "kind": "non_atomic_column"},
            "owner": "data-platform",
            "reason": "deliberate evidence envelope",
        }
    ]
    summary = build_normalization_report(_JSONB_SNAPSHOT, waivers=waivers)["summary"]
    assert summary["findings_by_evidence_class"].get("waived") == 1
    assert summary["relations_needing_review"] == 0
    assert "waived" in summary["headline"]


def test_empty_snapshot_yields_a_stable_no_relations_report() -> None:
    report = build_normalization_report(None)
    assert report["summary"]["relations_assessed"] == 0
    assert "No base relations" in report["summary"]["headline"]
    assert report["findings"] == []
