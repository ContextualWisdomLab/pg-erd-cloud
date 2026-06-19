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
