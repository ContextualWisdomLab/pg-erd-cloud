from __future__ import annotations

from app.ddl.export import snapshot_json_to_sql


def test_snapshot_export_preserves_table_tablespace() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "r",
                    "tablespace_name": "fast_space",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                    "is_not_null": True,
                }
            ],
        }
    )

    assert 'CREATE TABLE IF NOT EXISTS "public"."events" (' in sql
    assert ') TABLESPACE "fast_space";' in sql


def test_snapshot_export_preserves_index_tablespace() -> None:
    sql = snapshot_json_to_sql(
        {
            "indexes": [
                {
                    "index_def": "CREATE INDEX events_id_idx ON public.events USING btree (id)",
                    "index_tablespace_name": "fast_space",
                }
            ]
        }
    )

    assert (
        'CREATE INDEX CONCURRENTLY events_id_idx ON public.events USING btree (id) TABLESPACE "fast_space";'
        in sql
    )


def test_snapshot_export_preserves_unique_index_with_concurrently() -> None:
    sql = snapshot_json_to_sql(
        {
            "indexes": [
                {
                    "index_def": "CREATE UNIQUE INDEX users_email_key ON public.users USING btree (email)",
                }
            ]
        }
    )

    assert (
        "CREATE UNIQUE INDEX CONCURRENTLY users_email_key ON public.users USING btree (email);"
        in sql
    )
    assert "CREATE UNIQUE INDEX CONCURRENTLY CONCURRENTLY" not in sql


def test_snapshot_export_preserves_partition_parent_and_child() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "p",
                    "is_partition": False,
                    "partition_key": "RANGE (created_at)",
                },
                {
                    "schema_name": "public",
                    "relation_name": "events_2026",
                    "relation_oid": 2,
                    "relation_kind": "r",
                    "is_partition": True,
                    "partition_parent_schema": "public",
                    "partition_parent_name": "events",
                    "partition_bound": "FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')",
                },
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "created_at",
                    "data_type": "date",
                    "is_not_null": True,
                }
            ],
        }
    )

    assert (
        'CREATE TABLE IF NOT EXISTS "public"."events" (\n'
        '  "created_at" date NOT NULL\n'
        ') PARTITION BY RANGE (created_at);'
    ) in sql
    assert (
        'CREATE TABLE IF NOT EXISTS "public"."events_2026" PARTITION OF "public"."events" '
        "FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');"
    ) in sql


def test_snapshot_export_can_target_snowflake_from_postgres_snapshot() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 10,
                    "relation_kind": "r",
                    "tablespace_name": "fast_space",
                }
            ],
            "columns": [
                {
                    "relation_oid": 10,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                    "is_not_null": True,
                    "has_default": True,
                    "default_expr": "nextval('orders_id_seq'::regclass)",
                },
                {
                    "relation_oid": 10,
                    "column_position": 2,
                    "column_name": "amount",
                    "data_type": "numeric(12,2)",
                    "is_not_null": False,
                },
                {
                    "relation_oid": 10,
                    "column_position": 3,
                    "column_name": "payload",
                    "data_type": "jsonb",
                    "is_not_null": False,
                },
                {
                    "relation_oid": 10,
                    "column_position": 4,
                    "column_name": "created_at",
                    "data_type": "timestamp with time zone",
                    "is_not_null": True,
                    "has_default": True,
                    "default_expr": "now()",
                },
            ],
            "constraints": [
                {
                    "relation_oid": 10,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_pkey",
                    "constraint_type": "p",
                    "constraint_def": "PRIMARY KEY (id)",
                    "constrained_attnums": [1],
                },
                {
                    "relation_oid": 10,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_amount_check",
                    "constraint_type": "c",
                    "constraint_def": "CHECK (amount >= 0)",
                },
            ],
            "indexes": [
                {
                    "index_name": "orders_amount_idx",
                    "table_schema_name": "public",
                    "table_name": "orders",
                    "index_def": "CREATE INDEX orders_amount_idx ON public.orders (amount)",
                }
            ],
        },
        target_dialect="snowflake",
    )

    assert "-- Generated by pg-erd-cloud (MVP) for Snowflake" in sql
    assert 'CREATE SCHEMA IF NOT EXISTS "public";' in sql
    assert '  "id" NUMBER(10,0) NOT NULL,' in sql
    assert "nextval" not in sql
    assert '  "amount" NUMBER(12,2),' in sql
    assert '  "payload" VARIANT,' in sql
    assert (
        '  "created_at" TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP() NOT NULL,'
        in sql
    )
    assert '  CONSTRAINT "orders_pkey" PRIMARY KEY ("id")' in sql
    assert (
        '-- NOTE: skipped PostgreSQL CHECK constraint "orders_amount_check"'
        in sql
    )
    assert (
        '-- NOTE: PostgreSQL index "orders_amount_idx" on "public"."orders"'
        in sql
    )


def test_snapshot_export_can_target_postgresql_from_snowflake_snapshot() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "PUBLIC",
                    "relation_name": "EVENTS",
                    "relation_oid": 20,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 20,
                    "column_position": 1,
                    "column_name": "EVENT_ID",
                    "data_type": "NUMBER(38,0)",
                    "is_not_null": True,
                },
                {
                    "relation_oid": 20,
                    "column_position": 2,
                    "column_name": "PAYLOAD",
                    "data_type": "VARIANT",
                    "is_not_null": False,
                },
                {
                    "relation_oid": 20,
                    "column_position": 3,
                    "column_name": "CREATED_AT",
                    "data_type": "TIMESTAMP_NTZ",
                    "is_not_null": False,
                },
            ],
        }
    )

    assert 'CREATE TABLE IF NOT EXISTS "PUBLIC"."EVENTS" (' in sql
    assert '  "EVENT_ID" numeric(38,0) NOT NULL,' in sql
    assert '  "PAYLOAD" jsonb,' in sql
    assert '  "CREATED_AT" timestamp without time zone' in sql

def test_snapshot_source_dialect_fallback() -> None:
    from app.ddl.export import _snapshot_source_dialect

    assert _snapshot_source_dialect({"source_dialect": "invalid"}) == "postgresql"
    assert _snapshot_source_dialect({"dialect": "unknown"}) == "postgresql"
    assert _snapshot_source_dialect({}) == "postgresql"
