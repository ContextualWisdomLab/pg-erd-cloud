from __future__ import annotations

from app.ddl.migration import snapshot_diff_to_migration_sql


def _snap(relations, columns, pk_columns=None, fk_edges=None):
    return {
        "relations": relations,
        "columns": columns,
        "pk_columns": pk_columns or [],
        "fk_edges": fk_edges or [],
    }


def _member_table(oid=1):
    return _snap(
        relations=[
            {"relation_oid": oid, "schema_name": "public", "relation_name": "member"}
        ],
        columns=[
            {"relation_oid": oid, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": oid, "column_name": "email", "data_type": "varchar(100)", "is_not_null": False},
        ],
        pk_columns=[{"relation_oid": oid, "column_name": "member_id", "column_ordinal": 1}],
    )


def test_identical_snapshots_report_no_changes_even_with_different_oids():
    sql = snapshot_diff_to_migration_sql(_member_table(1), _member_table(999))
    assert "No schema changes" in sql


def test_added_table_emits_create_table_with_pk():
    base = _snap(relations=[], columns=[])
    sql = snapshot_diff_to_migration_sql(base, _member_table())
    assert 'CREATE TABLE "public"."member"' in sql
    assert '"member_id" bigint NOT NULL' in sql
    assert '"email" varchar(100)' in sql
    assert 'PRIMARY KEY ("member_id")' in sql


def test_dropped_table_emits_drop_table():
    base = _member_table()
    target = _snap(relations=[], columns=[])
    sql = snapshot_diff_to_migration_sql(base, target)
    assert 'DROP TABLE IF EXISTS "public"."member";' in sql


def test_added_and_dropped_columns():
    base = _member_table()
    target = _snap(
        relations=[{"relation_oid": 2, "schema_name": "public", "relation_name": "member"}],
        columns=[
            {"relation_oid": 2, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            # email dropped, nickname added
            {"relation_oid": 2, "column_name": "nickname", "data_type": "text", "is_not_null": False},
        ],
        pk_columns=[{"relation_oid": 2, "column_name": "member_id", "column_ordinal": 1}],
    )
    sql = snapshot_diff_to_migration_sql(base, target)
    assert 'ALTER TABLE "public"."member" ADD COLUMN "nickname" text;' in sql
    assert 'ALTER TABLE "public"."member" DROP COLUMN "email";' in sql


def test_column_type_and_nullability_changes():
    base = _member_table()
    target = _snap(
        relations=[{"relation_oid": 3, "schema_name": "public", "relation_name": "member"}],
        columns=[
            {"relation_oid": 3, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            # email: varchar(100) -> text, and now NOT NULL
            {"relation_oid": 3, "column_name": "email", "data_type": "text", "is_not_null": True},
        ],
        pk_columns=[{"relation_oid": 3, "column_name": "member_id", "column_ordinal": 1}],
    )
    sql = snapshot_diff_to_migration_sql(base, target)
    assert 'ALTER TABLE "public"."member" ALTER COLUMN "email" TYPE text;' in sql
    assert 'ALTER TABLE "public"."member" ALTER COLUMN "email" SET NOT NULL;' in sql


def test_foreign_key_add_and_drop():
    orders_rel = {"relation_oid": 2, "schema_name": "public", "relation_name": "orders"}
    orders_cols = [
        {"relation_oid": 2, "column_name": "order_id", "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 2, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
    ]
    fk = {
        "fk_constraint_name": "fk_orders_member",
        "child_relation_oid": 2,
        "parent_relation_oid": 1,
        "child_column_name": "member_id",
        "parent_column_name": "member_id",
        "column_ordinal": 1,
    }
    base = _snap(
        relations=[
            {"relation_oid": 1, "schema_name": "public", "relation_name": "member"},
            orders_rel,
        ],
        columns=[
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            *orders_cols,
        ],
    )
    target = _snap(
        relations=base["relations"],
        columns=base["columns"],
        fk_edges=[fk],
    )
    add_sql = snapshot_diff_to_migration_sql(base, target)
    assert (
        'ALTER TABLE "public"."orders" ADD CONSTRAINT "fk_orders_member" '
        'FOREIGN KEY ("member_id") REFERENCES "public"."member" ("member_id");'
        in add_sql
    )
    drop_sql = snapshot_diff_to_migration_sql(target, base)
    assert 'ALTER TABLE "public"."orders" DROP CONSTRAINT "fk_orders_member";' in drop_sql


def test_snowflake_dialect_uses_set_data_type():
    base = _member_table()
    target = _snap(
        relations=[{"relation_oid": 5, "schema_name": "public", "relation_name": "member"}],
        columns=[
            {"relation_oid": 5, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 5, "column_name": "email", "data_type": "text", "is_not_null": False},
        ],
        pk_columns=[{"relation_oid": 5, "column_name": "member_id", "column_ordinal": 1}],
    )
    sql = snapshot_diff_to_migration_sql(base, target, target_dialect="snowflake")
    assert "SET DATA TYPE" in sql
    assert "-- Migration (snowflake)" in sql
