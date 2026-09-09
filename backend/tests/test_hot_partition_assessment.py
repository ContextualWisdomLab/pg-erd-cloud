"""Golden-fixture tests for :mod:`app.spec.hot_partition_assessment`."""

from __future__ import annotations

from typing import Any

from app.spec.hot_partition_assessment import (
    ASSESSMENT_VERSION,
    assess_hot_partitions,
)


def _relation(
    oid: int,
    name: str,
    *,
    kind: str = "r",
    schema: str = "public",
    partition_key: str | None = None,
    is_partition: bool = False,
) -> dict[str, Any]:
    """Build one relation record in the introspection snapshot shape."""

    return {
        "relation_oid": oid,
        "schema_name": schema,
        "relation_name": name,
        "relation_kind": kind,
        "partition_key": partition_key,
        "is_partition": is_partition,
    }


def _column(
    oid: int,
    position: int,
    name: str,
    data_type: str,
    *,
    not_null: bool = False,
    has_default: bool = False,
    default_expr: str | None = None,
) -> dict[str, Any]:
    """Build one column record in the introspection snapshot shape."""

    return {
        "relation_oid": oid,
        "column_position": position,
        "column_name": name,
        "data_type": data_type,
        "is_not_null": not_null,
        "has_default": has_default,
        "default_expr": default_expr,
    }


def _kinds(result: dict[str, Any], relation: str) -> set[str]:
    """Return the finding kinds for ``relation``."""

    return {
        f["kind"] for f in result["findings"] if f["relation"]["name"] == relation
    }


def _finding(result: dict[str, Any], relation: str, kind: str) -> dict[str, Any] | None:
    """Return the first finding for ``relation``/``kind`` or ``None``."""

    for f in result["findings"]:
        if f["relation"]["name"] == relation and f["kind"] == kind:
            return f
    return None


def _queue_snapshot() -> dict[str, Any]:
    return {
        "relations": [_relation(1, "job_queue")],
        "columns": [
            _column(1, 1, "job_id", "bigint", not_null=True, has_default=True, default_expr="nextval('job_queue_job_id_seq'::regclass)"),
            _column(1, 2, "enqueued_at", "timestamp with time zone", not_null=True, has_default=True, default_expr="now()"),
            _column(1, 3, "status", "text", not_null=True),
            _column(1, 4, "payload", "jsonb", not_null=True),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "job_id"}],
    }


def test_queue_table_flags_append_heavy_unbounded_retention_and_monotonic_key() -> None:
    result = assess_hot_partitions(_queue_snapshot())
    assert result["version"] == ASSESSMENT_VERSION
    kinds = _kinds(result, "job_queue")
    assert "append_heavy_table" in kinds
    assert "unbounded_retention" in kinds
    assert "monotonic_key_hot_page" in kinds
    assert _finding(result, "job_queue", "append_heavy_table")["evidence_class"] == "inferred"
    assert _finding(result, "job_queue", "monotonic_key_hot_page")["evidence_class"] == "declared"
    record = next(r for r in result["relation_assessments"] if r["relation"]["name"] == "job_queue")
    assert record["risk"] == "review"
    assert "append_heavy" in record["signals"]


def test_capacity_profile_promotes_findings_to_proposed() -> None:
    profile = {
        "expected_rows": {"job_queue": 500_000_000},
        "retention_days": {"job_queue": 30},
        "write_concentration_keys": {"job_queue": ["status"]},
    }
    result = assess_hot_partitions(_queue_snapshot(), capacity_profile=profile)
    assert result["capacity_profile_applied"] is True
    assert _finding(result, "job_queue", "append_heavy_table")["evidence_class"] == "proposed"
    assert _finding(result, "job_queue", "unbounded_retention")["evidence_class"] == "proposed"
    assert "30 days" in _finding(result, "job_queue", "unbounded_retention")["next_action"]


def test_retention_column_suppresses_the_unbounded_retention_finding() -> None:
    snap = _queue_snapshot()
    snap["columns"].append(_column(1, 5, "archived_at", "timestamp with time zone"))
    result = assess_hot_partitions(snap)
    kinds = _kinds(result, "job_queue")
    assert "append_heavy_table" in kinds
    assert "unbounded_retention" not in kinds


def test_event_log_without_serial_key_still_flags_append_heavy_via_time_column() -> None:
    snap = {
        "relations": [_relation(1, "audit_event")],
        "columns": [
            _column(1, 1, "audit_event_uuid", "uuid", not_null=True),
            _column(1, 2, "occurred_at", "timestamp with time zone", not_null=True, has_default=True, default_expr="now()"),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "audit_event_uuid"}],
    }
    result = assess_hot_partitions(snap)
    assert "append_heavy_table" in _kinds(result, "audit_event")
    assert "monotonic_key_hot_page" not in _kinds(result, "audit_event")


def test_partitioned_table_whose_unique_key_omits_partition_key_is_flagged() -> None:
    snap = {
        "relations": [
            _relation(1, "measurement", partition_key="RANGE (recorded_at)")
        ],
        "columns": [
            _column(1, 1, "measurement_id", "bigint", not_null=True),
            _column(1, 2, "recorded_at", "timestamp with time zone", not_null=True),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "measurement_id"}],
        "constraints": [
            {
                "relation_oid": 1,
                "constraint_type": "u",
                "constraint_name": "measurement_measurement_id_key",
                "constrained_attnums": [1],
            }
        ],
    }
    result = assess_hot_partitions(snap)
    finding = _finding(result, "measurement", "partition_semantics_review")
    assert finding is not None
    assert finding["evidence_class"] == "declared"
    assert finding["confidence"] == "high"


def test_partitioned_table_with_partition_key_in_unique_is_not_flagged() -> None:
    snap = {
        "relations": [
            _relation(1, "measurement", partition_key="RANGE (recorded_at)")
        ],
        "columns": [
            _column(1, 1, "measurement_id", "bigint", not_null=True),
            _column(1, 2, "recorded_at", "timestamp with time zone", not_null=True),
        ],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "measurement_id"},
            {"relation_oid": 1, "column_name": "recorded_at"},
        ],
        "constraints": [
            {
                "relation_oid": 1,
                "constraint_type": "p",
                "constraint_name": "measurement_pkey",
                "constrained_attnums": [1, 2],
            }
        ],
    }
    result = assess_hot_partitions(snap)
    assert "partition_semantics_review" not in _kinds(result, "measurement")
    record = next(r for r in result["relation_assessments"] if r["relation"]["name"] == "measurement")
    assert record["partition_state"] == "partitioned"
    assert "partition_semantics_ok" in record["signals"]


def test_tenant_scoped_growing_table_flags_skew_candidate() -> None:
    snap = {
        "relations": [_relation(1, "schema_snapshot")],
        "columns": [
            _column(1, 1, "schema_snapshot_id", "bigint", not_null=True, has_default=True, default_expr="nextval('s'::regclass)"),
            _column(1, 2, "project_space_uuid", "uuid", not_null=True),
            _column(1, 3, "created_at", "timestamp with time zone", not_null=True),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "schema_snapshot_id"}],
    }
    result = assess_hot_partitions(snap)
    finding = _finding(result, "schema_snapshot", "skew_candidate")
    assert finding is not None
    assert finding["evidence_class"] == "inferred"
    assert finding["confidence"] == "low"


def test_ordinary_reference_table_has_no_findings() -> None:
    snap = {
        "relations": [_relation(1, "country_code")],
        "columns": [
            _column(1, 1, "country_code", "text", not_null=True),
            _column(1, 2, "country_name", "text", not_null=True),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "country_code"}],
    }
    result = assess_hot_partitions(snap)
    assert result["findings"] == []
    record = result["relation_assessments"][0]
    assert record["risk"] == "ok"
    assert record["partition_state"] == "unpartitioned"


def test_views_are_skipped_and_empty_snapshot_is_stable() -> None:
    assert assess_hot_partitions({"relations": [_relation(1, "v", kind="v")], "columns": [_column(1, 1, "x", "int")]})["findings"] == []
    empty = assess_hot_partitions(None)
    assert empty["relation_assessments"] == []
    assert empty["findings"] == []
    assert empty["capacity_profile_applied"] is False


def test_output_is_deterministic() -> None:
    snap = _queue_snapshot()
    snap["relations"].append(_relation(2, "app_user"))
    snap["columns"].append(_column(2, 1, "user_id", "bigint", not_null=True))
    snap["pk_columns"].append({"relation_oid": 2, "column_name": "user_id"})
    first = assess_hot_partitions(snap)
    assert first == assess_hot_partitions(snap)
    names = [f["relation"]["name"] for f in first["findings"]]
    assert names == sorted(names)
