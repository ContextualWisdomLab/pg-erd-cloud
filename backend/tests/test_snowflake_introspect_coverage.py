import pytest
from app.snowflake_introspect.introspect import (
    _int_or_none,
    _parse_snowflake_dsn,
    _connect,
    _fetch_dicts,
    _snowflake_relation_kind,
    _format_snowflake_data_type,
    _table_key,
    _constraint_type,
    _constraint_def,
    _build_constraints,
)


def test_int_or_none():
    assert _int_or_none("42") == 42
    assert _int_or_none("abc") is None


@pytest.mark.asyncio
async def test_parse_snowflake_dsn_invalid():
    with pytest.raises(ValueError, match="Snowflake DSN must use the snowflake scheme"):
        await _parse_snowflake_dsn("postgres://user:pass@acct/db")
    with pytest.raises(
        ValueError, match="Snowflake DSN must include an account identifier"
    ):
        await _parse_snowflake_dsn("snowflake://")
    with pytest.raises(ValueError, match="Snowflake DSN must include a user"):
        await _parse_snowflake_dsn("snowflake://acct")
    with pytest.raises(
        ValueError, match="Snowflake DSN must include a database path segment"
    ):
        await _parse_snowflake_dsn("snowflake://user:pass@acct")
    with pytest.raises(
        ValueError, match="Snowflake DSN path must be /database or /database/schema"
    ):
        await _parse_snowflake_dsn("snowflake://user:pass@acct/db/schema/extra")
    with pytest.raises(
        ValueError, match="Snowflake DSN query parameter is blank: warehouse"
    ):
        await _parse_snowflake_dsn("snowflake://user:pass@acct/db?warehouse=")


def test_connect(monkeypatch):
    import importlib

    def fake_import_module(name):
        raise ImportError("No module named snowflake.connector")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    with pytest.raises(
        RuntimeError, match="Snowflake reverse engineering requires the optional"
    ):
        _connect()


def test_fetch_dicts():
    class FakeCursor:
        def execute(self, sql, params):
            pass

        def fetchall(self):
            return [{"col1": "val1"}, {"col2": "val2"}]

    assert _fetch_dicts(FakeCursor(), "sql") == [{"col1": "val1"}, {"col2": "val2"}]


def test_snowflake_relation_kind():
    assert _snowflake_relation_kind("MATERIALIZED VIEW") == "m"
    assert _snowflake_relation_kind("TABLE") == "r"


def test_format_snowflake_data_type():
    assert _format_snowflake_data_type({"data_type": "VARCHAR"}) == "VARCHAR"
    assert (
        _format_snowflake_data_type({"data_type": "NUMBER", "numeric_precision": 10})
        == "NUMBER(10,0)"
    )


def test_table_key():
    assert _table_key({"table_schema": "SCHEMA", "table_name": "TABLE"}) == (
        "SCHEMA",
        "TABLE",
    )
    assert _table_key({}) == ("", "")


def test_constraint_type():
    assert _constraint_type("PRIMARY KEY") == "p"
    assert _constraint_type("UNIQUE") == "u"
    assert _constraint_type("FOREIGN KEY") == "f"
    assert _constraint_type("UNKNOWN") is None


def test_constraint_def():
    assert _constraint_def("p", ["col1"], None, None, []) == 'PRIMARY KEY ("col1")'
    assert _constraint_def("u", ["col1"], None, None, []) == 'UNIQUE ("col1")'
    assert (
        _constraint_def("f", ["col1"], "SCHEMA", "TABLE", ["ref_col"])
        == 'FOREIGN KEY ("col1") REFERENCES "SCHEMA"."TABLE" ("ref_col")'
    )


def test_build_constraints():
    constraints, pk_columns, fk_edges = _build_constraints(
        [
            {
                "constraint_type": "PRIMARY KEY",
                "table_schema": "SCHEMA",
                "table_name": "TABLE",
                "constraint_name": "PK_TABLE",
                "column_name": "col1",
                "ordinal_position": 1,
            },
            {
                "constraint_type": "FOREIGN KEY",
                "table_schema": "SCHEMA",
                "table_name": "TABLE",
                "constraint_name": "FK_TABLE",
                "column_name": "col2",
                "ordinal_position": 1,
                "referenced_table_schema": "SCHEMA",
                "referenced_table_name": "REF_TABLE",
                "referenced_column_name": "ref_col",
            },
        ],
        {("SCHEMA", "TABLE"): 1, ("SCHEMA", "REF_TABLE"): 2},
        {("SCHEMA", "TABLE"): {"col1": 1, "col2": 2}},
    )
    assert len(constraints) == 2
    assert len(pk_columns) == 1
    assert len(fk_edges) == 1

    constraints, pk_columns, fk_edges = _build_constraints(
        [
            {
                "constraint_type": "PRIMARY KEY",
                "table_schema": "SCHEMA",
                "table_name": "TABLE",
                "constraint_name": "PK_TABLE",
                "column_name": "col1",
                "ordinal_position": 1,
            }
        ],
        {},
        {("SCHEMA", "TABLE"): {"col1": 1}},
    )
    assert len(constraints) == 0


def test_fetch_dicts_empty():
    class FakeCursor:
        def execute(self, sql, params):
            pass

        def fetchall(self):
            return []

    assert _fetch_dicts(FakeCursor(), "sql") == []


def test_connect_success(monkeypatch):
    import importlib

    class FakeConnector:
        def connect(self, **kwargs):
            return "connected"

    def fake_import_module(name):
        return FakeConnector()

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    assert _connect() == "connected"


def test_format_snowflake_data_type_unmatched():
    assert _format_snowflake_data_type({"data_type": "BOOLEAN"}) == "BOOLEAN"


def test_constraint_def_unmatched():
    assert _constraint_def("c", ["col1"], None, None, []) == 'FOREIGN KEY ("col1")'


def test_build_constraints_missing_fields():
    constraints, pk_columns, fk_edges = _build_constraints(
        [
            {
                "constraint_type": "PRIMARY KEY",
                "table_schema": "SCHEMA",
                "table_name": "TABLE",
                "constraint_name": None,
                "column_name": "col1",
                "ordinal_position": 1,
            }
        ],
        {("SCHEMA", "TABLE"): 1},
        {("SCHEMA", "TABLE"): {"col1": 1}},
    )
    assert len(constraints) == 0

    constraints, pk_columns, fk_edges = _build_constraints(
        [
            {
                "constraint_type": None,
                "table_schema": "SCHEMA",
                "table_name": "TABLE",
                "constraint_name": "PK_TABLE",
                "column_name": "col1",
                "ordinal_position": 1,
            }
        ],
        {("SCHEMA", "TABLE"): 1},
        {("SCHEMA", "TABLE"): {"col1": 1}},
    )
    assert len(constraints) == 0


def test_build_constraints_fk_missing_columns():
    constraints, pk_columns, fk_edges = _build_constraints(
        [
            {
                "constraint_type": "FOREIGN KEY",
                "table_schema": "SCHEMA",
                "table_name": "TABLE",
                "constraint_name": "FK_TABLE",
                "column_name": None,
                "ordinal_position": 1,
                "referenced_table_schema": "SCHEMA",
                "referenced_table_name": "REF_TABLE",
                "referenced_column_name": None,
            }
        ],
        {("SCHEMA", "TABLE"): 1, ("SCHEMA", "REF_TABLE"): 2},
        {("SCHEMA", "TABLE"): {"col1": 1, "col2": 2}},
    )
    assert len(fk_edges) == 0


from app.snowflake_introspect.introspect import (
    _introspect_snowflake_sync_with_config,
    SnowflakeDsnConfig,
)


def test_introspect_snowflake_sync_with_config_missing_schema_filter(monkeypatch):
    class FakeCursor:
        def execute(self, sql, params):
            pass

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    def fake_connect(**kwargs):
        return FakeConnection()

    monkeypatch.setattr("app.snowflake_introspect.introspect._connect", fake_connect)

    def fake_fetch_dicts(cursor, sql, params=()):
        if "information_schema.columns" in sql.lower():
            return [
                {
                    "table_schema": "SCHEMA",
                    "table_name": "TABLE",
                    "column_name": "col",
                    "ordinal_position": 1,
                },
                {
                    "table_schema": "SCHEMA",
                    "table_name": "TABLE2",
                    "column_name": "col2",
                    "ordinal_position": None,
                },
            ]
        elif "information_schema.tables" in sql.lower():
            return [{"table_schema": "SCHEMA", "table_name": "TABLE"}]
        return []

    monkeypatch.setattr(
        "app.snowflake_introspect.introspect._fetch_dicts", fake_fetch_dicts
    )

    config = SnowflakeDsnConfig(
        account="acct",
        user="user",
        password=None,
        database="db",
        schema=None,
        warehouse=None,
        role=None,
        authenticator=None,
    )
    snapshot = _introspect_snowflake_sync_with_config(config, schema_filter=None)
    assert snapshot["database_name"] == "db"


def test_build_constraints_missing_relation():
    constraints, pk_columns, fk_edges = _build_constraints(
        [
            {
                "constraint_type": "PRIMARY KEY",
                "table_schema": "SCHEMA",
                "table_name": "UNKNOWN_TABLE",
                "constraint_name": "PK_TABLE",
                "column_name": "col1",
                "ordinal_position": 1,
            }
        ],
        {("SCHEMA", "TABLE"): 1},
        {("SCHEMA", "TABLE"): {"col1": 1}},
    )
    assert len(constraints) == 0


def test_introspect_snowflake_sync_with_config_missing_column_position(monkeypatch):
    class FakeCursor:
        def execute(self, sql, params):
            pass

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    def fake_connect(**kwargs):
        return FakeConnection()

    monkeypatch.setattr("app.snowflake_introspect.introspect._connect", fake_connect)

    def fake_fetch_dicts(cursor, sql, params=()):
        if "information_schema.columns" in sql.lower():
            return [
                {
                    "table_schema": "SCHEMA",
                    "table_name": "TABLE",
                    "column_name": None,
                    "ordinal_position": 1,
                }
            ]
        elif "information_schema.tables" in sql.lower():
            return [{"table_schema": "SCHEMA", "table_name": "TABLE"}]
        return []

    monkeypatch.setattr(
        "app.snowflake_introspect.introspect._fetch_dicts", fake_fetch_dicts
    )

    config = SnowflakeDsnConfig(
        account="acct",
        user="user",
        password=None,
        database="db",
        schema=None,
        warehouse=None,
        role=None,
        authenticator=None,
    )
    snapshot = _introspect_snowflake_sync_with_config(config, schema_filter=None)
    assert snapshot["database_name"] == "db"


def test_build_constraints_missing_ctype():
    constraints, pk_columns, fk_edges = _build_constraints(
        [
            {
                "constraint_type": "UNKNOWN_TYPE",
                "table_schema": "SCHEMA",
                "table_name": "TABLE",
                "constraint_name": "PK_TABLE",
                "column_name": "col1",
                "ordinal_position": 1,
            }
        ],
        {("SCHEMA", "TABLE"): 1},
        {("SCHEMA", "TABLE"): {"col1": 1}},
    )
    assert len(constraints) == 0
