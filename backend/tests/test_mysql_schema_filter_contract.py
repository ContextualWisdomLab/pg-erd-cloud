from __future__ import annotations

from app.mysql_introspect import introspect as mysql_introspect


def _metadata_sql() -> tuple[str, ...]:
    return (
        mysql_introspect._TABLES_SQL,
        mysql_introspect._COLUMNS_SQL,
        mysql_introspect._KEY_USAGE_SQL,
        mysql_introspect._INDEXES_SQL,
    )


def test_explicit_schema_filter_is_bound_without_changing_sql_structure() -> None:
    hostile_schema = "schema' OR '1'='1"

    params = mysql_introspect._schema_filter_params(hostile_schema)

    assert params[:3] == (hostile_schema, hostile_schema, hostile_schema)
    assert params[3:] == mysql_introspect._SYSTEM_SCHEMAS
    for sql in _metadata_sql():
        assert hostile_schema not in sql
        assert "TABLE_SCHEMA = %s" in sql
        assert "TABLE_SCHEMA NOT IN (%s, %s, %s, %s)" in sql


def test_default_schema_filter_excludes_system_schemas_through_parameters() -> None:
    params = mysql_introspect._schema_filter_params(None)

    assert params[:3] == (None, None, None)
    assert params[3:] == mysql_introspect._SYSTEM_SCHEMAS
    for sql in _metadata_sql():
        assert "TABLE_SCHEMA = %s" in sql
        assert "TABLE_SCHEMA NOT IN (%s, %s, %s, %s)" in sql


def test_empty_schema_filter_keeps_default_exclusion_semantics() -> None:
    assert mysql_introspect._schema_filter_params("") == (
        None,
        None,
        None,
        *mysql_introspect._SYSTEM_SCHEMAS,
    )
