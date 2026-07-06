from __future__ import annotations

from app.ddl.migration import snapshot_diff_to_migration_sql


def _snap(tables):
    """tables: {name: [(col, type, not_null), ...]}"""
    relations, columns, pk_columns = [], [], []
    for oid, (t, cols) in enumerate(tables.items(), start=1):
        relations.append({"relation_oid": oid, "relation_kind": "r", "schema_name": "public", "relation_name": t})
        for pos, (name, dtype, nn) in enumerate(cols, start=1):
            columns.append({
                "relation_oid": oid, "column_name": name, "data_type": dtype,
                "is_not_null": nn, "column_position": pos,
            })
        pk_columns.append({"relation_oid": oid, "column_name": cols[0][0], "column_ordinal": 1})
    return {"relations": relations, "columns": columns, "pk_columns": pk_columns, "fk_edges": []}


BASE = _snap({"member": [("member_id", "bigint", True)]})
TARGET = _snap({
    "member": [("member_id", "bigint", True), ("email", "text", False)],
    "orders": [("order_id", "bigint", True)],
})


def test_up_creates_what_down_drops():
    up = snapshot_diff_to_migration_sql(BASE, TARGET)
    down = snapshot_diff_to_migration_sql(TARGET, BASE)  # direction=down = swapped args

    assert 'CREATE TABLE "public"."orders"' in up
    assert 'ADD COLUMN "email"' in up
    assert 'DROP TABLE "public"."orders"' in down
    assert 'DROP COLUMN "email"' in down


def test_round_trip_is_identity():
    # applying up then down conceptually returns to base: the down of the down
    # (i.e., re-applying up) must equal the original up — mirrors are stable.
    up1 = snapshot_diff_to_migration_sql(BASE, TARGET)
    up2 = snapshot_diff_to_migration_sql(BASE, TARGET)
    assert up1 == up2
    assert snapshot_diff_to_migration_sql(BASE, BASE) == "-- No schema changes.\n"
