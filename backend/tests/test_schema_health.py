from __future__ import annotations

from app.spec.schema_health import analyze_schema_health


def _cats(report):
    return {(i["category"], i["severity"]) for i in report["items"]}


def test_flags_table_without_primary_key():
    snap = {
        "relations": [{"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "log"}],
        "columns": [{"relation_oid": 1, "column_name": "msg", "data_type": "text", "is_not_null": False}],
        "pk_columns": [],
        "fk_edges": [],
        "indexes": [],
    }
    report = analyze_schema_health(snap)
    assert ("no_primary_key", "warning") in _cats(report)
    assert report["summary"]["tables_analyzed"] == 1


def test_flags_unindexed_foreign_key_but_not_indexed_one():
    base = {
        "relations": [
            {"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 2, "relation_kind": "r", "schema_name": "public", "relation_name": "orders"},
        ],
        "columns": [],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "member_id"},
            {"relation_oid": 2, "column_name": "order_id"},
        ],
        "fk_edges": [
            {"child_relation_oid": 2, "parent_relation_oid": 1, "child_column_name": "member_id", "parent_column_name": "member_id"},
        ],
        "indexes": [],
    }
    # No index on orders.member_id -> flagged
    assert ("unindexed_foreign_key", "warning") in _cats(analyze_schema_health(base))

    # Add a covering index -> not flagged
    with_index = {**base, "indexes": [
        {"relation_oid": 2, "index_name": "ix_orders_member", "index_def": "CREATE INDEX ix_orders_member ON public.orders USING btree (member_id)"},
    ]}
    assert ("unindexed_foreign_key", "warning") not in _cats(analyze_schema_health(with_index))


def test_fk_column_that_is_pk_is_not_flagged_unindexed():
    # child FK column is itself the child's PK (auto-indexed)
    snap = {
        "relations": [
            {"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 2, "relation_kind": "r", "schema_name": "public", "relation_name": "profile"},
        ],
        "columns": [],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "member_id"},
            {"relation_oid": 2, "column_name": "member_id"},
        ],
        "fk_edges": [
            {"child_relation_oid": 2, "parent_relation_oid": 1, "child_column_name": "member_id", "parent_column_name": "member_id"},
        ],
        "indexes": [],
    }
    assert ("unindexed_foreign_key", "warning") not in _cats(analyze_schema_health(snap))


def test_flags_orphan_table_and_sorts_warnings_first():
    snap = {
        "relations": [
            {"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "island"},
            {"relation_oid": 2, "relation_kind": "r", "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 3, "relation_kind": "r", "schema_name": "public", "relation_name": "orders"},
        ],
        "columns": [],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "id"},
            {"relation_oid": 2, "column_name": "member_id"},
            {"relation_oid": 3, "column_name": "order_id"},
        ],
        "fk_edges": [
            {"child_relation_oid": 3, "parent_relation_oid": 2, "child_column_name": "member_id", "parent_column_name": "member_id"},
        ],
        "indexes": [],
    }
    report = analyze_schema_health(snap)
    cats = _cats(report)
    assert ("orphan_table", "info") in cats  # 'island' connects to nothing
    severities = [i["severity"] for i in report["items"]]
    assert severities == sorted(severities, key={"warning": 0, "info": 1}.get)


def test_views_are_not_flagged_and_empty_snapshot():
    snap = {
        "relations": [{"relation_oid": 9, "relation_kind": "v", "schema_name": "public", "relation_name": "v_report"}],
        "columns": [], "pk_columns": [], "fk_edges": [], "indexes": [],
    }
    assert analyze_schema_health(snap)["items"] == []
    assert analyze_schema_health({})["items"] == []
