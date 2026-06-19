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
        'CREATE INDEX events_id_idx ON public.events USING btree (id) TABLESPACE "fast_space";'
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
