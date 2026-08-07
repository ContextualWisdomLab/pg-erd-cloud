"""Edge-case coverage for small, pure schema-analysis helpers."""

from __future__ import annotations

from app.spec.audit_columns import check_audit_columns
from app.spec.fk_cycles import detect_fk_cycles
from app.spec.naming_lint import lint_naming
from app.spec.schema_stats import compute_schema_stats
from app.spec.sensitive_columns import detect_sensitive_columns


def test_audit_columns_ignores_columns_from_non_table_relations() -> None:
    """Exclude view-only columns from table audit-adoption evidence."""
    report = check_audit_columns(
        {
            "relations": [
                {
                    "relation_oid": 7,
                    "relation_kind": "v",
                    "schema_name": "public",
                    "relation_name": "buyer_view",
                }
            ],
            "columns": [{"relation_oid": 7, "column_name": "created_at"}],
        }
    )

    assert report["items"] == []
    assert report["summary"]["tables"] == 0
    assert report["summary"]["with_created"] == 0


def test_fk_cycle_detector_ignores_edges_with_unknown_relations() -> None:
    """Drop malformed foreign-key edges whose relation OIDs are not in the snapshot."""
    report = detect_fk_cycles(
        {
            "relations": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "known_table",
                }
            ],
            "fk_edges": [
                {"child_relation_oid": 999, "parent_relation_oid": 1},
                {"child_relation_oid": 1, "parent_relation_oid": 998},
            ],
        }
    )

    assert report["items"] == []
    assert report["summary"] == {
        "circular_dependencies": 0,
        "self_references": 0,
        "total": 0,
    }


def test_sensitive_column_detector_skips_empty_names() -> None:
    """Do not classify absent or empty column names as personal data evidence."""
    report = detect_sensitive_columns(
        {
            "relations": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "buyer_record",
                }
            ],
            "columns": [
                {"relation_oid": 1, "column_name": None},
                {"relation_oid": 1, "column_name": ""},
            ],
        }
    )

    assert report["items"] == []
    assert report["summary"]["total"] == 0


def test_naming_lint_tolerates_non_list_snapshot_sections() -> None:
    """Treat malformed relation/column containers as no naming rows."""
    report = lint_naming({"relations": {}, "columns": "not-a-list"})

    assert report["items"] == []
    assert report["summary"] == {
        "high": 0,
        "info": 0,
        "total": 0,
        "dominant_case": None,
    }


def test_schema_stats_ignores_blank_data_types() -> None:
    """Count the column while omitting a blank type from the type distribution."""
    report = compute_schema_stats(
        {
            "relations": [
                {
                    "relation_oid": 1,
                    "relation_kind": "r",
                    "schema_name": "public",
                    "relation_name": "buyer_record",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_name": "record_value",
                    "data_type": "   ",
                    "is_not_null": False,
                }
            ],
        }
    )

    assert report["columns"]["total"] == 1
    assert report["data_types"] == {}
