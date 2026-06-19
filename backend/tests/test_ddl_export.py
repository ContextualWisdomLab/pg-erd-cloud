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
