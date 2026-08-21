from __future__ import annotations

from app.ddl.migration_safety import analyze_migration_safety


def _snap(relations, columns, pk_columns=None, fk_edges=None):
    return {
        "relations": relations,
        "columns": columns,
        "pk_columns": pk_columns or [],
        "fk_edges": fk_edges or [],
    }


def _member(oid=1, email_not_null=False):
    return _snap(
        relations=[{"relation_oid": oid, "schema_name": "public", "relation_name": "member"}],
        columns=[
            {"relation_oid": oid, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": oid, "column_name": "email", "data_type": "varchar(100)", "is_not_null": email_not_null},
        ],
        pk_columns=[{"relation_oid": oid, "column_name": "member_id", "column_ordinal": 1}],
    )


def _cats(analysis):
    return {(i["category"], i["severity"]) for i in analysis["items"]}


def test_no_changes_is_empty_and_not_blocking():
    a = analyze_migration_safety(_member(1), _member(999))
    assert a["items"] == []
    assert a["summary"]["has_blocking"] is False


def test_drop_table_and_column_are_destructive():
    base = _member()
    # target: member table gone entirely
    empty = _snap(relations=[], columns=[])
    a = analyze_migration_safety(base, empty)
    assert ("drop_table", "destructive") in _cats(a)
    assert a["summary"]["has_destructive"] is True

    # target: email column dropped
    dropped_col = _snap(
        relations=[{"relation_oid": 2, "schema_name": "public", "relation_name": "member"}],
        columns=[{"relation_oid": 2, "column_name": "member_id", "data_type": "bigint", "is_not_null": True}],
        pk_columns=[{"relation_oid": 2, "column_name": "member_id"}],
    )
    a2 = analyze_migration_safety(base, dropped_col)
    assert ("drop_column", "destructive") in _cats(a2)


def test_add_nullable_is_safe_add_not_null_is_warning():
    base = _member()
    # add nullable column
    add_nullable = _snap(
        relations=[{"relation_oid": 3, "schema_name": "public", "relation_name": "member"}],
        columns=[
            {"relation_oid": 3, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 3, "column_name": "email", "data_type": "varchar(100)", "is_not_null": False},
            {"relation_oid": 3, "column_name": "nickname", "data_type": "text", "is_not_null": False},
        ],
        pk_columns=[{"relation_oid": 3, "column_name": "member_id"}],
    )
    assert ("add_column", "safe") in _cats(analyze_migration_safety(base, add_nullable))

    # add NOT NULL column
    add_nn = _snap(
        relations=[{"relation_oid": 4, "schema_name": "public", "relation_name": "member"}],
        columns=[
            {"relation_oid": 4, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 4, "column_name": "email", "data_type": "varchar(100)", "is_not_null": False},
            {"relation_oid": 4, "column_name": "status", "data_type": "text", "is_not_null": True},
        ],
        pk_columns=[{"relation_oid": 4, "column_name": "member_id"}],
    )
    assert ("add_column", "warning") in _cats(analyze_migration_safety(base, add_nn))


def test_type_change_and_set_not_null_are_warnings():
    base = _member(email_not_null=False)
    target = _snap(
        relations=[{"relation_oid": 5, "schema_name": "public", "relation_name": "member"}],
        columns=[
            {"relation_oid": 5, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            # email: varchar(100) -> text AND now NOT NULL
            {"relation_oid": 5, "column_name": "email", "data_type": "text", "is_not_null": True},
        ],
        pk_columns=[{"relation_oid": 5, "column_name": "member_id"}],
    )
    cats = _cats(analyze_migration_safety(base, target))
    assert ("alter_column_type", "warning") in cats
    assert ("set_not_null", "warning") in cats


def test_add_fk_is_warning_drop_fk_is_safe_and_report_is_sorted():
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
        relations=[{"relation_oid": 1, "schema_name": "public", "relation_name": "member"}, orders_rel],
        columns=[{"relation_oid": 1, "column_name": "member_id", "data_type": "bigint", "is_not_null": True}, *orders_cols],
        pk_columns=[{"relation_oid": 1, "column_name": "member_id"}],
    )
    target = _snap(relations=base["relations"], columns=base["columns"], pk_columns=base["pk_columns"], fk_edges=[fk])

    add = analyze_migration_safety(base, target)
    assert ("add_foreign_key", "warning") in _cats(add)

    drop = analyze_migration_safety(target, base)
    assert ("drop_foreign_key", "safe") in _cats(drop)

    # destructive/warnings should sort before safe items
    mixed_target = _snap(
        relations=[orders_rel],  # member dropped (destructive), fk gone (safe)
        columns=orders_cols,
        pk_columns=[{"relation_oid": 2, "column_name": "order_id"}],
    )
    mixed = analyze_migration_safety(target, mixed_target)
    severities = [i["severity"] for i in mixed["items"]]
    assert severities == sorted(severities, key={"destructive": 0, "warning": 1, "safe": 2}.get)
