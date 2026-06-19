from __future__ import annotations

from app.pg_introspect import queries


def test_columns_query_captures_postgresql_type_catalog_metadata() -> None:
    sql = queries.COLUMNS_SQL

    assert "pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type" in sql
    assert "JOIN pg_catalog.pg_type typ ON typ.oid = a.atttypid" in sql
    assert "typ_ns.nspname AS type_schema" in sql
    assert "typ.typname AS type_name" in sql
    assert "typ.typtype::text AS type_kind" in sql
    assert "typ.typcategory::text AS type_category" in sql
    assert "pg_catalog.format_type(typ.typbasetype, typ.typtypmod)" in sql
    assert "pg_catalog.format_type(typ.typelem, -1)" in sql
    assert "a.attndims AS array_dimensions" in sql


def test_indexes_query_captures_dynamic_index_method_metadata() -> None:
    sql = queries.INDEXES_SQL

    assert "tbl.oid AS relation_oid" in sql
    assert "JOIN pg_catalog.pg_am am ON am.oid = idx.relam" in sql
    assert "am.amname AS access_method" in sql
    assert "am_ext.extname AS access_method_extension" in sql
    assert "operator_classes" in sql
    assert "operator_class_extensions" in sql
    assert "pg_catalog.pg_opclass" in sql
    assert "pg_catalog.pg_extension" in sql
    assert "pg_catalog.pg_get_indexdef(idx.oid) AS index_def" in sql


def test_queries_capture_explicit_tablespaces() -> None:
    assert "rel_ts.spcname AS tablespace_name" in queries.RELATIONS_SQL
    assert "LEFT JOIN pg_catalog.pg_tablespace rel_ts" in queries.RELATIONS_SQL
    assert "idx_ts.spcname AS index_tablespace_name" in queries.INDEXES_SQL
    assert "LEFT JOIN pg_catalog.pg_tablespace idx_ts" in queries.INDEXES_SQL


def test_relations_query_captures_partition_metadata() -> None:
    sql = queries.RELATIONS_SQL

    assert "pg_catalog.obj_description(c.oid, 'pg_class') AS relation_comment" in sql
    assert "pg_catalog.pg_get_partkeydef(c.oid) AS partition_key" in sql
    assert "pg_catalog.pg_get_expr(c.relpartbound, c.oid) AS partition_bound" in sql
    assert "parent.oid AS partition_parent_oid" in sql
    assert "parent_ns.nspname AS partition_parent_schema" in sql
    assert "parent.relname AS partition_parent_name" in sql
    assert "LEFT JOIN pg_catalog.pg_inherits inh ON inh.inhrelid = c.oid" in sql
