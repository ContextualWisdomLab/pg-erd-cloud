from __future__ import annotations

from app.diff.schema_diff import diff_snapshots


def _snap(relations, columns, pk_columns=None, fk_edges=None):
    return {
        "relations": relations,
        "columns": columns,
        "pk_columns": pk_columns or [],
        "fk_edges": fk_edges or [],
    }


def _base():
    return _snap(
        relations=[
            {"relation_oid": 1, "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 2, "schema_name": "public", "relation_name": "orders"},
        ],
        columns=[
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 1, "column_name": "email", "data_type": "varchar(100)", "is_not_null": False},
            {"relation_oid": 2, "column_name": "order_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 2, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
        ],
        pk_columns=[
            {"relation_oid": 1, "column_name": "member_id", "column_ordinal": 1},
            {"relation_oid": 2, "column_name": "order_id", "column_ordinal": 1},
        ],
        fk_edges=[
            {
                "fk_constraint_oid": 10,
                "fk_constraint_name": "fk_orders_member",
                "child_relation_oid": 2,
                "parent_relation_oid": 1,
                "child_column_name": "member_id",
                "parent_column_name": "member_id",
                "column_ordinal": 1,
            }
        ],
    )


def test_identical_snapshots_report_no_changes_even_with_different_oids():
    # Same logical schema, but re-introspection assigned different oids.
    # A correct diff keys by name and must report zero changes.
    base = _base()
    target = _snap(
        relations=[
            {"relation_oid": 900, "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 901, "schema_name": "public", "relation_name": "orders"},
        ],
        columns=[
            {"relation_oid": 900, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 900, "column_name": "email", "data_type": "varchar(100)", "is_not_null": False},
            {"relation_oid": 901, "column_name": "order_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 901, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
        ],
        pk_columns=[
            {"relation_oid": 900, "column_name": "member_id", "column_ordinal": 1},
            {"relation_oid": 901, "column_name": "order_id", "column_ordinal": 1},
        ],
        fk_edges=[
            {
                "fk_constraint_oid": 77,
                "fk_constraint_name": "fk_orders_member",
                "child_relation_oid": 901,
                "parent_relation_oid": 900,
                "child_column_name": "member_id",
                "parent_column_name": "member_id",
                "column_ordinal": 1,
            }
        ],
    )
    d = diff_snapshots(base, target)
    assert d["summary"]["has_changes"] is False
    assert d["tables"]["added"] == []
    assert d["tables"]["removed"] == []
    assert d["tables"]["changed"] == []
    assert d["foreign_keys"]["added"] == []
    assert d["foreign_keys"]["removed"] == []


def test_table_added_and_removed():
    base = _base()
    target = _snap(
        relations=[
            {"relation_oid": 1, "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 3, "schema_name": "public", "relation_name": "audit_log"},
        ],
        columns=[
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 1, "column_name": "email", "data_type": "varchar(100)", "is_not_null": False},
            {"relation_oid": 3, "column_name": "id", "data_type": "bigint", "is_not_null": True},
        ],
        pk_columns=[{"relation_oid": 1, "column_name": "member_id", "column_ordinal": 1}],
    )
    d = diff_snapshots(base, target)
    assert d["tables"]["added"] == ["public.audit_log"]
    assert d["tables"]["removed"] == ["public.orders"]
    assert d["summary"]["tables_added"] == 1
    assert d["summary"]["tables_removed"] == 1
    # The removed FK (only existed in base) is reported.
    assert d["summary"]["fks_removed"] == 1


def test_column_added_removed_type_and_nullability_changed():
    base = _base()
    target = _snap(
        relations=[
            {"relation_oid": 1, "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 2, "schema_name": "public", "relation_name": "orders"},
        ],
        columns=[
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            # email: type widened AND became NOT NULL (a change)
            {"relation_oid": 1, "column_name": "email", "data_type": "varchar(255)", "is_not_null": True},
            # new column added
            {"relation_oid": 1, "column_name": "phone", "data_type": "varchar(20)", "is_not_null": False},
            {"relation_oid": 2, "column_name": "order_id", "data_type": "bigint", "is_not_null": True},
            # orders.member_id removed
        ],
        pk_columns=[
            {"relation_oid": 1, "column_name": "member_id", "column_ordinal": 1},
            {"relation_oid": 2, "column_name": "order_id", "column_ordinal": 1},
        ],
    )
    d = diff_snapshots(base, target)
    changed = {c["table"]: c for c in d["tables"]["changed"]}
    assert set(changed) == {"public.member", "public.orders"}

    member = changed["public.member"]
    assert member["columns"]["added"] == ["phone"]
    email_change = next(c for c in member["columns"]["changed"] if c["column"] == "email")
    assert email_change["from"] == {"data_type": "varchar(100)", "is_not_null": False}
    assert email_change["to"] == {"data_type": "varchar(255)", "is_not_null": True}

    orders = changed["public.orders"]
    assert orders["columns"]["removed"] == ["member_id"]
    assert d["summary"]["columns_added"] == 1
    assert d["summary"]["columns_removed"] == 1
    assert d["summary"]["columns_changed"] == 1


def test_primary_key_change_detected():
    base = _base()
    target = _snap(
        relations=[{"relation_oid": 1, "schema_name": "public", "relation_name": "member"}],
        columns=[
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 1, "column_name": "email", "data_type": "varchar(100)", "is_not_null": False},
        ],
        # PK moved from member_id to email
        pk_columns=[{"relation_oid": 1, "column_name": "email", "column_ordinal": 1}],
    )
    d = diff_snapshots(base, target)
    member = next(c for c in d["tables"]["changed"] if c["table"] == "public.member")
    assert member["primary_key"] == {"from": ["member_id"], "to": ["email"]}


def test_column_default_change_is_detected():
    base = _snap(
        relations=[
            {
                "relation_oid": 1,
                "schema_name": "public",
                "relation_name": "email_records",
            }
        ],
        columns=[
            {
                "relation_oid": 1,
                "column_name": "source_lineage_json",
                "data_type": "json",
                "is_not_null": True,
                "has_default": False,
                "default_expr": None,
            }
        ],
    )
    target = _snap(
        relations=[
            {
                "relation_oid": 99,
                "schema_name": "public",
                "relation_name": "email_records",
            }
        ],
        columns=[
            {
                "relation_oid": 99,
                "column_name": "source_lineage_json",
                "data_type": "json",
                "is_not_null": True,
                "has_default": True,
                "default_expr": "'{}'::json",
            }
        ],
    )

    diff = diff_snapshots(base, target)

    change = diff["tables"]["changed"][0]["columns"]["changed"][0]
    assert change == {
        "column": "source_lineage_json",
        "from": {
            "data_type": "json",
            "is_not_null": True,
            "has_default": False,
            "default_expr": None,
        },
        "to": {
            "data_type": "json",
            "is_not_null": True,
            "has_default": True,
            "default_expr": "'{}'::json",
        },
    }
    assert diff["summary"]["columns_changed"] == 1


def test_fk_added():
    base = _snap(
        relations=[
            {"relation_oid": 1, "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 2, "schema_name": "public", "relation_name": "orders"},
        ],
        columns=[
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 2, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
        ],
    )
    target = _snap(
        relations=[
            {"relation_oid": 1, "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 2, "schema_name": "public", "relation_name": "orders"},
        ],
        columns=[
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 2, "column_name": "member_id", "data_type": "bigint", "is_not_null": True},
        ],
        fk_edges=[
            {
                "fk_constraint_name": "fk_orders_member",
                "child_relation_oid": 2,
                "parent_relation_oid": 1,
                "child_column_name": "member_id",
                "parent_column_name": "member_id",
                "column_ordinal": 1,
            }
        ],
    )
    d = diff_snapshots(base, target)
    assert d["summary"]["fks_added"] == 1
    added = d["foreign_keys"]["added"][0]
    assert added["child_table"] == "public.orders"
    assert added["parent_table"] == "public.member"
    assert added["child_columns"] == ["member_id"]


def test_none_and_empty_snapshots_are_safe():
    assert diff_snapshots(None, None)["summary"]["has_changes"] is False
    d = diff_snapshots(None, _base())
    assert d["summary"]["tables_added"] == 2
    assert diff_snapshots(_base(), None)["summary"]["tables_removed"] == 2


def test_diff_skips_orphan_nameless_rows_and_detects_comment_change():
    # Rows referencing an unknown relation_oid or missing a name must be skipped,
    # not treated as spurious changes; a table-comment change is a real change.
    base = _snap(
        relations=[
            {
                "relation_oid": 1,
                "schema_name": "public",
                "relation_name": "t",
                "relation_comment": "old note",
            }
        ],
        columns=[
            {"relation_oid": 1, "column_name": "id", "data_type": "int", "is_not_null": True},
            {"relation_oid": 999, "column_name": "ghost", "data_type": "int"},  # orphan oid
            {"relation_oid": 1, "column_name": None, "data_type": "int"},  # no name
        ],
        pk_columns=[
            {"relation_oid": 999, "column_name": "id", "column_ordinal": 1},  # orphan oid
            {"relation_oid": 1, "column_name": None, "column_ordinal": 1},  # no name
        ],
        fk_edges=[
            {
                "fk_constraint_name": "x",
                "child_relation_oid": 999,  # orphan child -> skipped
                "parent_relation_oid": 1,
                "child_column_name": "a",
                "parent_column_name": "b",
                "column_ordinal": 1,
            }
        ],
    )
    target = _snap(
        relations=[
            {
                "relation_oid": 1,
                "schema_name": "public",
                "relation_name": "t",
                "relation_comment": "new note",  # comment changed
            }
        ],
        columns=[
            {"relation_oid": 1, "column_name": "id", "data_type": "int", "is_not_null": True}
        ],
    )
    d = diff_snapshots(base, target)
    changed = d["tables"]["changed"]
    assert len(changed) == 1
    assert changed[0]["table"] == "public.t"
    assert changed[0]["comment"] == {"from": "old note", "to": "new note"}
    # orphan/nameless rows and the orphan FK produced no spurious changes
    assert changed[0]["columns"]["added"] == []
    assert changed[0]["columns"]["removed"] == []
    assert d["summary"]["fks_added"] == 0
    assert d["summary"]["fks_removed"] == 0
