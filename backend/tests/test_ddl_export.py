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

def test_snowflake_missing_schema_or_name() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "r",
                },
                {
                    "schema_name": "public",
                    "relation_oid": 2,
                    "relation_kind": "r",
                },
                {
                    "schema_name": "public",
                    "relation_name": "users",
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                }
            ],
        },
        target_dialect="snowflake"
    )
    assert 'CREATE TABLE' not in sql

def test_snapshot_export_missing_schema_or_name() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "r",
                },
                {
                    "schema_name": "public",
                    "relation_oid": 2,
                    "relation_kind": "r",
                },
                {
                    "schema_name": "public",
                    "relation_name": "users",
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                }
            ],
        }
    )
    assert 'CREATE TABLE' not in sql

def test_snapshot_export_partition_without_key() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "p",
                }
            ]
        }
    )
    assert "-- NOTE: \"public\".\"events\" is partitioned; partition definition not included in MVP export" in sql

def test_snapshot_export_foreign_keys() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "fk_user",
                    "constraint_type": "f",
                    "constraint_def": "FOREIGN KEY (user_id) REFERENCES users(id)",
                }
            ]
        }
    )
    assert "-- Foreign keys" in sql
    assert "ALTER TABLE \"public\".\"orders\" ADD CONSTRAINT \"fk_user\" FOREIGN KEY (user_id) REFERENCES users(id);" in sql

def test_snapshot_export_invalid_foreign_key() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "fk_user",
                    "constraint_type": "f",
                }
            ]
        }
    )
    assert "-- Foreign keys" in sql
    assert "ALTER TABLE" not in sql

def test_snapshot_export_invalid_index() -> None:
    sql = snapshot_json_to_sql(
        {
            "indexes": [
                {
                    "index_tablespace_name": "fast_space",
                }
            ]
        }
    )
    assert "-- Indexes" in sql
    assert "CREATE INDEX" not in sql

def test_snowflake_export_invalid_foreign_key() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "fk_user",
                    "constraint_type": "f",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- Foreign keys" in sql
    assert "ALTER TABLE" not in sql

def test_snowflake_export_invalid_index() -> None:
    sql = snapshot_json_to_sql(
        {
            "indexes": [
                {
                    "index_tablespace_name": "fast_space",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- Indexes" in sql
    assert "-- NOTE: PostgreSQL index metadata is not emitted for Snowflake." in sql

def test_snowflake_export_skipped_check_constraint() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "amount_check",
                    "constraint_type": "c",
                    "constraint_def": "CHECK (amount > 0)",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- NOTE: skipped PostgreSQL CHECK constraint \"amount_check\" on \"public\".\"orders\" for Snowflake export." in sql

def test_snapshot_export_skip_columns_without_name() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "data_type": "integer",
                }
            ],
        }
    )
    assert 'CREATE TABLE IF NOT EXISTS "public"."events" (\n)' in sql

def test_snowflake_export_skip_columns_without_name() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "data_type": "integer",
                }
            ],
        },
        target_dialect="snowflake"
    )
    assert 'CREATE TABLE IF NOT EXISTS "public"."events" (\n);' in sql

def test_snowflake_export_partition_metadata() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "p",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- NOTE: skipped PostgreSQL partition metadata on \"public\".\"events\" for Snowflake export." in sql

def test_snapshot_export_inline_constraints() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_pkey",
                    "constraint_type": "p",
                    "constraint_def": "PRIMARY KEY (id)",
                },
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_amount_check",
                    "constraint_type": "c",
                    "constraint_def": "CHECK (amount >= 0)",
                },
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_uuid_key",
                    "constraint_type": "u",
                    "constraint_def": "UNIQUE (uuid)",
                },
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "invalid_constraint",
                    "constraint_type": "x",
                    "constraint_def": "INVALID",
                },
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_type": "c",
                    "constraint_def": "CHECK (amount >= 0)",
                }
            ]
        }
    )
    assert 'CONSTRAINT "orders_pkey" PRIMARY KEY (id)' in sql
    assert 'CONSTRAINT "orders_amount_check" CHECK (amount >= 0)' in sql
    assert 'CONSTRAINT "orders_uuid_key" UNIQUE (uuid)' in sql
    assert 'INVALID' not in sql

def test_snowflake_export_inline_constraints() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_uuid_key",
                    "constraint_type": "u",
                    "constraint_def": "UNIQUE (uuid)",
                },
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "invalid_constraint",
                    "constraint_type": "x",
                    "constraint_def": "INVALID",
                },
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_type": "u",
                    "constraint_def": "UNIQUE (id)",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'CONSTRAINT "orders_uuid_key" UNIQUE (uuid)' in sql
    assert 'INVALID' not in sql

def test_snowflake_export_skipped_tablespace() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "r",
                    "tablespace_name": "fast_space"
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- NOTE: skipped PostgreSQL TABLESPACE \"fast_space\" on \"public\".\"events\" for Snowflake export." in sql

def test_snapshot_export_source_dialect_fallback() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                }
            ]
        }
    )
    assert 'CREATE TABLE IF NOT EXISTS "public"."events"' in sql

def test_snapshot_export_invalid_source_dialect() -> None:
    sql = snapshot_json_to_sql(
        {
            "dialect": "invalid_dialect",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ]
        }
    )
    assert 'CREATE TABLE IF NOT EXISTS "public"."events"' in sql

def test_snapshot_export_without_indexes_or_fks() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ]
        }
    )
    assert "-- Foreign keys" not in sql
    assert "-- Indexes" not in sql

def test_snowflake_export_inline_constraints_missing_column() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_pkey",
                    "constraint_type": "p",
                    "constraint_def": "PRIMARY KEY (id, missing)",
                    "constrained_attnums": [1, 2],
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'CONSTRAINT "orders_pkey" PRIMARY KEY (id, missing)' in sql

def test_snowflake_export_inline_constraints_invalid_attnum() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_pkey",
                    "constraint_type": "p",
                    "constraint_def": "PRIMARY KEY (id)",
                    "constrained_attnums": ["invalid"],
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'CONSTRAINT "orders_pkey" PRIMARY KEY (id)' in sql

def test_snowflake_export_default_expr() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                    "has_default": True,
                    "default_expr": "100",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'DEFAULT 100' in sql

def test_snapshot_export_default_expr() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                    "has_default": True,
                    "default_expr": "100",
                }
            ]
        }
    )
    assert 'DEFAULT 100' in sql

def test_snapshot_export_partition_bound() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events_2026",
                    "relation_oid": 2,
                    "relation_kind": "r",
                    "is_partition": True,
                    "partition_parent_schema": "public",
                    "partition_parent_name": "events",
                    "partition_bound": "FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')",
                }
            ]
        }
    )
    assert 'PARTITION OF "public"."events" FOR VALUES FROM (\'2026-01-01\') TO (\'2027-01-01\');' in sql

def test_snapshot_export_partition_without_parent_schema() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events_2026",
                    "relation_oid": 2,
                    "relation_kind": "r",
                    "is_partition": True,
                    "partition_parent_name": "events",
                    "partition_bound": "FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')",
                }
            ]
        }
    )
    assert 'PARTITION OF "public"."events"' not in sql
    assert 'CREATE TABLE IF NOT EXISTS "public"."events_2026"' in sql

def test_snowflake_export_foreign_keys() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "fk_user",
                    "constraint_type": "f",
                    "constraint_def": "FOREIGN KEY (user_id) REFERENCES users(id)",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- Foreign keys" in sql
    assert "ALTER TABLE \"public\".\"orders\" ADD CONSTRAINT \"fk_user\" FOREIGN KEY (user_id) REFERENCES users(id);" in sql

def test_snowflake_export_invalid_foreign_key_fields() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "fk_user",
                    "constraint_type": "f",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- Foreign keys" in sql
    assert "ALTER TABLE" not in sql

def test_snowflake_mapped_data_types() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "USER-DEFINED",
                    "domain_base_type": "integer",
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "jsonb[]",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "numeric(10,2)",
                    "numeric_precision": 10,
                    "numeric_scale": 2,
                },
                {
                    "relation_oid": 1,
                    "column_position": 4,
                    "column_name": "c4",
                    "data_type": "numeric(10)",
                    "numeric_precision": 10,
                },
                {
                    "relation_oid": 1,
                    "column_position": 5,
                    "column_name": "c5",
                    "data_type": "numeric",
                },
                {
                    "relation_oid": 1,
                    "column_position": 6,
                    "column_name": "c6",
                    "data_type": "character varying(255)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 7,
                    "column_name": "c7",
                    "data_type": "character(10)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 8,
                    "column_name": "c8",
                    "data_type": "timestamp without time zone",
                },
                {
                    "relation_oid": 1,
                    "column_position": 9,
                    "column_name": "c9",
                    "data_type": "time without time zone",
                },
                {
                    "relation_oid": 1,
                    "column_position": 10,
                    "column_name": "c10",
                    "data_type": 123, # Invalid type to hit missing lines
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" NUMBER(10,0)' in sql
    assert 'c2" ARRAY' in sql
    assert 'c3" NUMBER(10,2)' in sql
    assert 'c4" NUMBER(10,0)' in sql
    assert 'c5" NUMBER' in sql
    assert 'c6" VARCHAR(255)' in sql
    assert 'c7" CHAR(10)' in sql
    assert 'c8" TIMESTAMP_NTZ' in sql
    assert 'c9" TIME' in sql
    assert 'c10" VARCHAR' in sql

def test_postgresql_mapped_data_types() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "ARRAY",
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "VARIANT",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "FLOAT",
                },
                {
                    "relation_oid": 1,
                    "column_position": 4,
                    "column_name": "c4",
                    "data_type": "BINARY",
                },
                {
                    "relation_oid": 1,
                    "column_position": 5,
                    "column_name": "c5",
                    "data_type": "TIMESTAMP_TZ",
                },
                {
                    "relation_oid": 1,
                    "column_position": 6,
                    "column_name": "c6",
                    "data_type": "NUMBER(10,2)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 7,
                    "column_name": "c7",
                    "data_type": "VARCHAR(255)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 8,
                    "column_name": "c8",
                    "data_type": "CHAR(10)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 9,
                    "column_name": "c9",
                    "data_type": 123,
                }
            ]
        }
    )
    assert 'c1" jsonb' in sql
    assert 'c2" jsonb' in sql
    assert 'c3" double precision' in sql
    assert 'c4" bytea' in sql
    assert 'c5" timestamp with time zone' in sql
    assert 'c6" numeric(10,2)' in sql
    assert 'c7" character varying(255)' in sql
    assert 'c8" character(10)' in sql
    assert 'c9" text' in sql

def test_snowflake_mapped_data_types_fallbacks() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "USER-DEFINED",
                    "domain_base_type": 123,
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "USER-DEFINED",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR' in sql
    assert 'c2" VARCHAR' in sql
    assert 'c3" VARCHAR' in sql

def test_postgresql_data_type_fallbacks() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "USER-DEFINED",
                    "domain_base_type": 123,
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "USER-DEFINED",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                }
            ]
        }
    )
    assert 'c1" USER-DEFINED' in sql
    assert 'c2" USER-DEFINED' in sql
    assert 'c3" text' in sql

def test_snowflake_mapped_data_types_with_scales() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "USER-DEFINED",
                    "domain_base_type": "numeric(10,2)",
                    "numeric_precision": 10,
                    "numeric_scale": 2,
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "USER-DEFINED",
                    "domain_base_type": "numeric(10)",
                    "numeric_precision": 10,
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "USER-DEFINED",
                    "domain_base_type": "numeric",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" NUMBER(10,2)' in sql
    assert 'c2" NUMBER(10,0)' in sql
    assert 'c3" NUMBER' in sql

def test_snowflake_export_default_expr_fallbacks() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "date",
                    "has_default": True,
                    "default_expr": "CURRENT_DATE",
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "time without time zone",
                    "has_default": True,
                    "default_expr": "CURRENT_TIME",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "uuid",
                    "has_default": True,
                    "default_expr": "gen_random_uuid()",
                },
                {
                    "relation_oid": 1,
                    "column_position": 4,
                    "column_name": "c4",
                    "data_type": "text",
                    "has_default": True,
                    "default_expr": "something_else()",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'DEFAULT CURRENT_DATE()' in sql
    assert 'DEFAULT CURRENT_TIME()' in sql
    assert 'DEFAULT UUID_STRING()' in sql
    assert 'c4" VARCHAR' in sql # something_else() should be dropped

def test_snowflake_mapped_data_types_type_kind_e() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "USER-DEFINED",
                    "type_kind": "e",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR' in sql

def test_postgresql_mapped_data_types_type_kind_e() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "USER-DEFINED",
                    "type_kind": "e",
                }
            ]
        }
    )
    assert 'c1" USER-DEFINED' in sql

def test_postgresql_mapped_data_types_with_precision() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "NUMBER",
                    "numeric_precision": 10,
                    "numeric_scale": 2,
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "NUMBER",
                    "numeric_precision": 10,
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "NUMBER",
                }
            ]
        }
    )
    assert 'c1" numeric' in sql
    assert 'c2" numeric' in sql
    assert 'c3" numeric' in sql

def test_snowflake_mapped_data_types_type_kind_fallback() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "USER-DEFINED",
                    "type_kind": "something_else",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR' in sql

def test_column_default_clause_edge_cases() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "text",
                    "has_default": True,
                    "default_expr": 123,
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "text",
                    "has_default": True,
                    "default_expr": "   ",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "integer",
                    "has_default": True,
                    "default_expr": "-42.5",
                },
                {
                    "relation_oid": 1,
                    "column_position": 4,
                    "column_name": "c4",
                    "data_type": "text",
                    "has_default": True,
                    "default_expr": "'a string'",
                },
                {
                    "relation_oid": 1,
                    "column_position": 5,
                    "column_name": "c5",
                    "data_type": "boolean",
                    "has_default": True,
                    "default_expr": "TRUE",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR,' in sql # ignored due to wrong type
    assert 'c2" VARCHAR,' in sql # ignored due to empty string
    assert 'c3" NUMBER(10,0) DEFAULT -42.5' in sql
    assert 'c4" VARCHAR DEFAULT \'a string\'' in sql
    assert 'c5" BOOLEAN DEFAULT TRUE' in sql

def test_snapshot_export_invalid_data_type() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": 123,
                }
            ]
        }
    )
    assert 'c1" text' in sql

def test_snapshot_export_group_by_relation() -> None:
    from app.ddl.export import _group_by_relation
    assert _group_by_relation("not_a_list") == {}
    assert _group_by_relation([{"relation_oid": 1}, "not_a_dict"]) == {1: [{"relation_oid": 1}]}

def test_snowflake_export_inline_constraints_edge_cases() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "id",
                    "data_type": "integer",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_pkey",
                    "constraint_type": "p",
                    "constraint_def": "PRIMARY KEY (id)",
                    "constrained_attnums": "not_a_list",
                },
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_pkey_invalid",
                    "constraint_type": "p",
                    "constraint_def": "PRIMARY KEY (id)",
                    "constrained_attnums": ["invalid"],
                },
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "orders_pkey_missing_col",
                    "constraint_type": "p",
                    "constraint_def": "PRIMARY KEY (id)",
                    "constrained_attnums": [2],
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'CONSTRAINT "orders_pkey" PRIMARY KEY (id)' in sql

def test_snowflake_export_invalid_index_dict() -> None:
    sql = snapshot_json_to_sql(
        {
            "indexes": [
                "not_a_dict"
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- Indexes" in sql
    assert "-- NOTE:" not in sql

def test_column_default_clause_invalid() -> None:
    from app.ddl.export import _column_default_clause
    assert _column_default_clause(None, "postgresql") is None
    assert _column_default_clause("", "postgresql") is None
    assert _column_default_clause(" ", "postgresql") is None
    assert _column_default_clause("invalid", "snowflake") is None

def test_snapshot_source_dialect() -> None:
    from app.ddl.export import _snapshot_source_dialect
    assert _snapshot_source_dialect({"dialect": "postgres"}) == "postgresql"
    assert _snapshot_source_dialect({"database_dialect": "sf"}) == "snowflake"
    assert _snapshot_source_dialect({"database_dialect": "invalid", "dialect": "pg"}) == "postgresql"
    assert _snapshot_source_dialect({}) == "postgresql"

def test_snowflake_mapped_data_types_type_kind_e_recursive() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "USER-DEFINED",
                    "domain_base_type": "invalid",
                    "type_kind": "e",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR' in sql

def test_postgresql_export_missing_precision_for_numeric() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "numeric(10,2)",
                    "numeric_precision": 10,
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "numeric(10)",
                }
            ]
        }
    )
    assert 'c1" numeric(10,2)' in sql
    assert 'c2" numeric(10)' in sql

def test_snowflake_export_foreign_keys_with_missing_fields() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "orders",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "constraints": [
                {
                    "relation_oid": 1,
                    "schema_name": "public",
                    "relation_name": "orders",
                    "constraint_name": "fk_user",
                    "constraint_type": "f",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- Foreign keys" in sql
    assert "ALTER TABLE" not in sql

def test_snowflake_export_partition_metadata_with_all_fields() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "events",
                    "relation_oid": 1,
                    "relation_kind": "p",
                    "is_partition": True,
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert "-- NOTE: skipped PostgreSQL partition metadata on \"public\".\"events\" for Snowflake export." in sql

def test_postgresql_mapped_data_types_with_precision_scale_and_more() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "NUMBER",
                    "numeric_precision": 10,
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "VARCHAR(255)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "CHAR(10)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 4,
                    "column_name": "c4",
                    "data_type": "TIMESTAMP_TZ",
                }
            ]
        }
    )
    assert 'c1" numeric' in sql
    assert 'c2" character varying(255)' in sql
    assert 'c3" character(10)' in sql
    assert 'c4" timestamp with time zone' in sql

def test_snowflake_mapped_data_types_with_precision_scale_and_more() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "numeric(10,2)",
                    "numeric_precision": 10,
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "character varying",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "character",
                },
                {
                    "relation_oid": 1,
                    "column_position": 4,
                    "column_name": "c4",
                    "data_type": "timestamp",
                },
                {
                    "relation_oid": 1,
                    "column_position": 5,
                    "column_name": "c5",
                    "data_type": "time",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" NUMBER(10,2)' in sql
    assert 'c2" VARCHAR' in sql
    assert 'c3" CHAR' in sql
    assert 'c4" TIMESTAMP_NTZ' in sql
    assert 'c5" TIME' in sql

def test_snowflake_export_fallback_patterns() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "string(100)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "char(50)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "timestamp_tz",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR' in sql
    assert 'c2" CHAR(50)' in sql
    assert 'c3" TIMESTAMP_NTZ' in sql

def test_snowflake_export_fallback_patterns_2() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "varchar(100)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "char",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "timestamp",
                },
                {
                    "relation_oid": 1,
                    "column_position": 4,
                    "column_name": "c4",
                    "data_type": "time",
                },
                {
                    "relation_oid": 1,
                    "column_position": 5,
                    "column_name": "c5",
                    "data_type": "interval",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR(100)' in sql
    assert 'c2" CHAR' in sql
    assert 'c3" TIMESTAMP_NTZ' in sql
    assert 'c4" TIME' in sql
    assert 'c5" VARCHAR' in sql

def test_postgresql_mapped_data_types_fallback_patterns() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "string(100)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 2,
                    "column_name": "c2",
                    "data_type": "char(50)",
                },
                {
                    "relation_oid": 1,
                    "column_position": 3,
                    "column_name": "c3",
                    "data_type": "timestamp_tz",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR' in sql
    assert 'c2" CHAR(50)' in sql
    assert 'c3" TIMESTAMP_NTZ' in sql

def test_postgresql_export_missing_data_type() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": 123,
                }
            ]
        }
    )
    assert 'c1" text' in sql

def test_postgresql_export_missing_precision_for_numeric_edge_case() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "NUMBER",
                    "numeric_precision": 10,
                }
            ]
        }
    )
    assert 'c1" numeric' in sql

def test_postgresql_export_fallback_type() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "unknown_type",
                }
            ]
        }
    )
    assert 'c1" text' in sql

def test_mapped_data_type_same_dialect() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "postgresql",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "custom_type",
                }
            ]
        },
        target_dialect="postgresql"
    )
    assert 'c1" custom_type' in sql

def test_snowflake_mapped_data_types_fallback_no_str() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": None,
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR' in sql

def test_postgresql_mapped_data_types_fallback_no_str() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": None,
                }
            ]
        },
        target_dialect="postgresql"
    )
    assert 'c1" text' in sql

def test_snowflake_mapped_data_types_precision_no_scale() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "NUMBER",
                    "numeric_precision": 10,
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR' in sql

def test_postgresql_mapped_data_types_precision_no_scale() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "NUMBER",
                    "numeric_precision": 10,
                }
            ]
        },
        target_dialect="postgresql"
    )
    assert 'c1" NUMBER' in sql

def test_snowflake_mapped_data_types_fallback_no_str_final() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" VARCHAR' in sql

def test_postgresql_mapped_data_types_fallback_no_str_final() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                }
            ]
        },
        target_dialect="postgresql"
    )
    assert 'c1" text' in sql

def test_postgresql_mapped_data_types_precision_no_scale_final() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "NUMBER",
                    "numeric_precision": 10,
                }
            ]
        },
        target_dialect="postgresql"
    )
    assert 'c1" numeric' in sql

def test_mapped_data_type_same_dialect_final() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "postgresql",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "custom_type",
                }
            ]
        },
        target_dialect="postgresql"
    )
    assert 'c1" custom_type' in sql

def test_snowflake_to_snowflake_mapped_data_types() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "NUMBER",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" NUMBER' in sql

def test_postgresql_mapped_data_types_fallback_no_str_final_postgres() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": None,
                }
            ]
        },
        target_dialect="postgresql"
    )
    assert 'c1" text' in sql

def test_snowflake_mapped_data_types_precision_no_scale_final_snowflake() -> None:
    sql = snapshot_json_to_sql(
        {
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "numeric",
                    "numeric_precision": 10,
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" NUMBER' in sql

def test_mapped_data_type_same_dialect_final_snowflake() -> None:
    sql = snapshot_json_to_sql(
        {
            "source_dialect": "snowflake",
            "relations": [
                {
                    "schema_name": "public",
                    "relation_name": "data_types",
                    "relation_oid": 1,
                    "relation_kind": "r",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_position": 1,
                    "column_name": "c1",
                    "data_type": "custom_type",
                }
            ]
        },
        target_dialect="snowflake"
    )
    assert 'c1" custom_type' in sql

def test_snowflake_mapped_data_types_fallback_no_str_final_final() -> None:
    from app.ddl.export import _postgres_type_to_snowflake
    assert _postgres_type_to_snowflake({"data_type": 123}) == "VARCHAR"

def test_postgresql_mapped_data_types_fallback_no_str_final_final() -> None:
    from app.ddl.export import _snowflake_type_to_postgres
    assert _snowflake_type_to_postgres({"data_type": 123}) == "text"

def test_postgresql_mapped_data_types_precision_no_scale_final_final() -> None:
    from app.ddl.export import _snowflake_type_to_postgres
    assert _snowflake_type_to_postgres({"data_type": "NUMBER", "numeric_precision": 10}) == "numeric"

def test_mapped_data_type_same_dialect_final_final() -> None:
    from app.ddl.export import _mapped_data_type
    assert _mapped_data_type({"data_type": "custom_type"}, "snowflake", "snowflake") == "custom_type"

def test_snowflake_type_to_postgres_regex_precision() -> None:
    from app.ddl.export import _snowflake_type_to_postgres
    assert _snowflake_type_to_postgres({"data_type": "NUMBER(10)"}) == "numeric(10,0)"

def test_mapped_data_type_same_dialect_returns_data_type() -> None:
    from app.ddl.export import _mapped_data_type
    assert _mapped_data_type({"data_type": "special_type"}, "snowflake", "snowflake") == "special_type"

def test_mapped_data_type_invalid_source_dialect() -> None:
    from app.ddl.export import _mapped_data_type
    assert _mapped_data_type({"data_type": "some_type"}, "invalid", "postgresql") == "some_type"
