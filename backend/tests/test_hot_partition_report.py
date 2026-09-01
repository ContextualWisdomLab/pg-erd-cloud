"""Tests for :mod:`app.spec.hot_partition_report` (the report envelope)."""

from __future__ import annotations

from typing import Any

from app.spec.hot_partition_report import REPORT_VERSION, build_hot_partition_report

_QUEUE_SNAPSHOT: dict[str, Any] = {
    "relations": [
        {"relation_oid": 1, "schema_name": "public", "relation_name": "job_queue", "relation_kind": "r", "partition_key": None, "is_partition": False}
    ],
    "columns": [
        {"relation_oid": 1, "column_position": 1, "column_name": "job_id", "data_type": "bigint", "is_not_null": True, "has_default": True, "default_expr": "nextval('s'::regclass)"},
        {"relation_oid": 1, "column_position": 2, "column_name": "enqueued_at", "data_type": "timestamp with time zone", "is_not_null": True, "has_default": True, "default_expr": "now()"},
    ],
    "pk_columns": [{"relation_oid": 1, "column_name": "job_id"}],
}

_REFERENCE_SNAPSHOT: dict[str, Any] = {
    "relations": [
        {"relation_oid": 1, "schema_name": "public", "relation_name": "country_code", "relation_kind": "r", "partition_key": None, "is_partition": False}
    ],
    "columns": [
        {"relation_oid": 1, "column_position": 1, "column_name": "country_code", "data_type": "text", "is_not_null": True},
        {"relation_oid": 1, "column_position": 2, "column_name": "country_name", "data_type": "text", "is_not_null": True},
    ],
    "pk_columns": [{"relation_oid": 1, "column_name": "country_code"}],
}


def test_envelope_is_additive_over_the_analyzer_output() -> None:
    report = build_hot_partition_report(_QUEUE_SNAPSHOT)
    assert report["report_version"] == REPORT_VERSION
    assert report["schema_fingerprint"].startswith("sha256:")
    assert "generated_at" in report
    assert report["version"] == "1"
    assert report["evidence_basis"] == "catalog_and_optional_capacity_profile"
    assert isinstance(report["findings"], list)


def test_summary_headline_flags_at_risk_relations_and_profile_state() -> None:
    summary = build_hot_partition_report(_QUEUE_SNAPSHOT)["summary"]
    assert summary["relations_assessed"] == 1
    assert summary["relations_at_risk"] == 1
    assert "no capacity profile" in summary["headline"]
    assert summary["findings_by_kind"].get("append_heavy_table") == 1

    profiled = build_hot_partition_report(
        _QUEUE_SNAPSHOT, capacity_profile={"retention_days": {"job_queue": 14}}
    )["summary"]
    assert "capacity profile applied" in profiled["headline"]
    assert profiled["findings_by_evidence_class"].get("proposed", 0) >= 1


def test_summary_headline_for_a_clean_schema() -> None:
    summary = build_hot_partition_report(_REFERENCE_SNAPSHOT)["summary"]
    assert summary["relations_at_risk"] == 0
    assert "no catalog-visible hot-partition" in summary["headline"] or "None of the" in summary["headline"]


def test_empty_snapshot_is_stable() -> None:
    report = build_hot_partition_report(None)
    assert report["summary"]["relations_assessed"] == 0
    assert report["findings"] == []
    assert report["capacity_profile_applied"] is False
