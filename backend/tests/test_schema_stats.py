from __future__ import annotations

from app.spec.schema_stats import compute_schema_stats


def _snap():
    return {
        "relations": [
            {"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 2, "relation_kind": "r", "schema_name": "public", "relation_name": "orders"},
            {"relation_oid": 3, "relation_kind": "v", "schema_name": "public", "relation_name": "v_report"},
        ],
        "columns": [
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 1, "column_name": "email", "data_type": "text", "is_not_null": True},
            {"relation_oid": 1, "column_name": "nickname", "data_type": "text", "is_not_null": False},
            {"relation_oid": 2, "column_name": "order_id", "data_type": "bigint", "is_not_null": True},
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "member_id"}],
        "fk_edges": [{"child_relation_oid": 2, "parent_relation_oid": 1, "child_column_name": "member_id", "parent_column_name": "member_id"}],
        "indexes": [{"relation_oid": 1, "index_name": "pk_member"}],
    }


def test_counts_relations_by_kind():
    s = compute_schema_stats(_snap())
    assert s["relations"]["table"] == 2
    assert s["relations"]["view"] == 1
    assert s["relations"]["total"] == 3


def test_column_stats_and_widest_table():
    s = compute_schema_stats(_snap())
    assert s["columns"]["total"] == 4
    assert s["columns"]["nullable"] == 1
    assert s["columns"]["not_null"] == 3
    assert s["columns"]["avg_per_table"] == 2.0  # 4 columns / 2 tables
    assert s["columns"]["max_per_table"] == 3    # member has 3
    assert s["widest_tables"][0] == {"table": "public.member", "columns": 3}


def test_constraint_and_pk_coverage():
    s = compute_schema_stats(_snap())
    assert s["constraints"]["primary_keys"] == 1
    assert s["constraints"]["foreign_keys"] == 1
    assert s["constraints"]["indexes"] == 1
    assert s["tables_without_primary_key"] == 1  # orders has no PK


def test_data_type_distribution_and_empty():
    s = compute_schema_stats(_snap())
    assert s["data_types"]["bigint"] == 2
    assert s["data_types"]["text"] == 2
    empty = compute_schema_stats({})
    assert empty["relations"]["total"] == 0
    assert empty["columns"]["avg_per_table"] == 0.0
