from __future__ import annotations

import copy

import pytest

from app.forward.migration_plan import compile_migration_plan


def _empty_model() -> dict:
    return {"format_version": 1, "postgresql_major": 18, "schemas": []}


def _table_model(*, nullable: bool = False, data_type: str = "bigint") -> dict:
    return {
        "format_version": 1,
        "postgresql_major": 18,
        "schemas": [
            {
                "schema_name": "Sales Data",
                "tables": [
                    {
                        "table_name": 'Order "Item"',
                        "comment": None,
                        "columns": [
                            {
                                "column_name": "Item ID",
                                "data_type": data_type,
                                "nullable": nullable,
                                "ordinal_position": 1,
                            }
                        ],
                        "primary_key": {
                            "constraint_name": 'Order "Item" pkey',
                            "columns": ["Item ID"],
                            "deferrable": False,
                            "initially_deferred": False,
                        },
                        "unique_constraints": [],
                        "foreign_keys": [],
                        "indexes": [],
                        "unsupported_features": [],
                    }
                ],
            }
        ],
    }


def test_plan_is_structured_deterministic_and_preserves_quoted_identifiers() -> None:
    first = compile_migration_plan(_empty_model(), _table_model())
    second = compile_migration_plan(_empty_model(), copy.deepcopy(_table_model()))

    assert first == second
    assert first["compiler_version"] == "pg-erd-forward/v1"
    assert first["snapshot_contract_version"] == 1
    assert first["can_dry_run"] is True
    assert len(first["plan_digest"]) == 64
    assert [statement["kind"] for statement in first["statements"]] == [
        "create_schema",
        "create_table",
    ]
    create_table = first["statements"][1]
    assert create_table["sql"] == (
        'CREATE TABLE "Sales Data"."Order ""Item""" '
        '("Item ID" bigint NOT NULL, CONSTRAINT "Order ""Item"" pkey" '
        'PRIMARY KEY ("Item ID"));'
    )
    assert create_table["transactional"] is True
    assert create_table["required_privileges"] == ["CREATE"]
    assert create_table["dependencies"] == ["schema:Sales Data"]


def test_destructive_drop_has_explicit_risk_and_recovery_boundary() -> None:
    target = _table_model()
    target["schemas"][0]["tables"][0]["columns"].append(
        {
            "column_name": "Legacy Value",
            "data_type": "text",
            "nullable": True,
            "ordinal_position": 2,
        }
    )
    plan = compile_migration_plan(target, _table_model())

    drop = next(item for item in plan["statements"] if item["kind"] == "drop_column")
    assert drop["risk"]["severity"] == "destructive"
    assert drop["risk"]["data_loss"] is True
    assert drop["risk"]["lock_mode"] == "ACCESS EXCLUSIVE"
    assert drop["reversible"] is False
    assert plan["risk_summary"]["destructive"] == 1
    assert plan["requires_destructive_confirmation"] is True


def test_type_and_not_null_changes_expose_preconditions_and_rewrite_warning() -> None:
    base = _table_model(nullable=True, data_type="integer")
    target = _table_model(nullable=False, data_type="bigint")
    base["schemas"][0]["tables"][0]["primary_key"] = None
    target["schemas"][0]["tables"][0]["primary_key"] = None

    plan = compile_migration_plan(base, target)

    type_change = next(
        item for item in plan["statements"] if item["kind"] == "alter_column_type"
    )
    not_null = next(
        item for item in plan["statements"] if item["kind"] == "set_not_null"
    )
    assert type_change["risk"]["possible_rewrite"] is True
    assert type_change["preconditions"][0]["kind"] == "castable_values"
    assert not_null["preconditions"] == [
        {
            "kind": "no_null_values",
            "schema_name": "Sales Data",
            "table_name": 'Order "Item"',
            "column_name": "Item ID",
        }
    ]


def test_existing_primary_key_change_is_a_blocker_not_silent_sql() -> None:
    target = _table_model()
    target["schemas"][0]["tables"][0]["primary_key"] = None

    plan = compile_migration_plan(_table_model(), target)

    assert plan["can_dry_run"] is False
    assert plan["statements"] == []
    assert plan["blockers"] == [
        {
            "code": "primary_key_change_unsupported",
            "object": 'Sales Data.Order "Item"',
            "object_ref": {
                "schema_name": "Sales Data",
                "table_name": 'Order "Item"',
            },
            "detail": "Changing an existing primary key is not supported by compiler v1.",
        }
    ]


def test_no_changes_produces_empty_executable_plan() -> None:
    model = _table_model()

    plan = compile_migration_plan(model, copy.deepcopy(model))

    assert plan["statements"] == []
    assert plan["blockers"] == []
    assert plan["can_dry_run"] is True
    assert plan["risk_summary"] == {
        "safe": 0,
        "warning": 0,
        "destructive": 0,
    }


def test_add_column_and_drop_table_paths_are_structured() -> None:
    base = _table_model()
    target = copy.deepcopy(base)
    target["schemas"][0]["tables"][0]["columns"].append(
        {
            "column_name": "Required Value",
            "data_type": "text",
            "nullable": False,
            "ordinal_position": 2,
        }
    )
    add_plan = compile_migration_plan(base, target)
    added = next(item for item in add_plan["statements"] if item["kind"] == "add_column")
    assert added["risk"]["severity"] == "warning"
    assert added["preconditions"][0]["kind"] == "table_is_empty"

    empty_schema = _empty_model()
    empty_schema["schemas"] = [{"schema_name": "Sales Data", "tables": []}]
    drop_plan = compile_migration_plan(base, empty_schema)
    assert drop_plan["statements"][0]["kind"] == "drop_table"
    assert drop_plan["requires_destructive_confirmation"] is True


def test_default_expressions_fail_closed_before_sql_rendering() -> None:
    target = _table_model()
    target["schemas"][0]["tables"][0]["columns"][0]["default"] = "now()"

    with pytest.raises(ValueError, match="default expressions"):
        compile_migration_plan(_empty_model(), target)


def test_nullable_add_and_drop_not_null_are_safe_paths() -> None:
    base = _table_model(nullable=False)
    base["schemas"][0]["tables"][0]["primary_key"] = None
    target = copy.deepcopy(base)
    target["schemas"][0]["tables"][0]["columns"][0]["nullable"] = True
    target["schemas"][0]["tables"][0]["columns"].append(
        {
            "column_name": "Optional Value",
            "data_type": "text",
            "nullable": True,
            "ordinal_position": 2,
        }
    )

    plan = compile_migration_plan(base, target)

    assert {item["kind"] for item in plan["statements"]} == {
        "add_column",
        "drop_not_null",
    }
    assert all(item["risk"]["severity"] == "safe" for item in plan["statements"])


def test_deferrable_primary_key_and_version_mismatch_paths() -> None:
    target = _table_model()
    target["schemas"][0]["tables"][0]["primary_key"].update(
        {"deferrable": True, "initially_deferred": True}
    )
    plan = compile_migration_plan(_empty_model(), target)
    assert "DEFERRABLE INITIALLY DEFERRED" in plan["statements"][1]["sql"]

    base = _empty_model()
    base["postgresql_major"] = 17
    blocked = compile_migration_plan(base, _empty_model())
    assert blocked["statements"] == []
    assert blocked["blockers"][0]["code"] == "postgresql_version_mismatch"


def test_create_table_without_pk_and_immediately_deferred_false_branch() -> None:
    without_pk = _table_model()
    without_pk["schemas"][0]["tables"][0]["primary_key"] = None
    no_pk_plan = compile_migration_plan(_empty_model(), without_pk)
    assert "PRIMARY KEY" not in no_pk_plan["statements"][1]["sql"]

    deferrable = _table_model()
    deferrable["schemas"][0]["tables"][0]["primary_key"].update(
        {"deferrable": True, "initially_deferred": False}
    )
    plan = compile_migration_plan(_empty_model(), deferrable)
    assert " DEFERRABLE" in plan["statements"][1]["sql"]
    assert "INITIALLY DEFERRED" not in plan["statements"][1]["sql"]


def test_comment_changes_are_blockers_until_comment_sql_is_supported() -> None:
    base = _table_model()
    target = copy.deepcopy(base)
    target["schemas"][0]["tables"][0]["comment"] = "new table comment"
    target["schemas"][0]["tables"][0]["columns"][0]["comment"] = "new column comment"

    plan = compile_migration_plan(base, target)

    assert plan["can_dry_run"] is False
    assert plan["statements"] == []
    assert {blocker["code"] for blocker in plan["blockers"]} == {
        "table_comment_change_unsupported",
        "column_comment_change_unsupported",
    }


def test_new_table_with_comments_is_blocked_instead_of_losing_semantics() -> None:
    target = _table_model()
    target["schemas"][0]["tables"][0]["comment"] = "must survive apply"

    plan = compile_migration_plan(_empty_model(), target)

    assert plan["can_dry_run"] is False
    assert plan["statements"] == []
    assert plan["blockers"][0]["code"] == "table_comment_change_unsupported"


def test_existing_column_reordering_is_an_explicit_blocker() -> None:
    base = _table_model()
    base_table = base["schemas"][0]["tables"][0]
    base_table["columns"].append(
        {
            "column_name": "Second Column",
            "data_type": "text",
            "nullable": True,
            "ordinal_position": 2,
        }
    )
    target = copy.deepcopy(base)
    target_columns = target["schemas"][0]["tables"][0]["columns"]
    target_columns[0]["ordinal_position"] = 2
    target_columns[1]["ordinal_position"] = 1

    plan = compile_migration_plan(base, target)

    assert plan["can_dry_run"] is False
    assert plan["statements"] == []
    assert plan["blockers"][0]["code"] == "column_order_change_unsupported"


def test_schema_removal_is_blocked_instead_of_leaving_an_empty_schema() -> None:
    plan = compile_migration_plan(_table_model(), _empty_model())

    assert plan["can_dry_run"] is False
    assert plan["statements"] == []
    assert plan["blockers"] == [
        {
            "code": "schema_removal_unsupported",
            "object": "Sales Data",
            "object_ref": {"schema_name": "Sales Data"},
            "detail": "Removing an existing schema is not supported by compiler v1.",
        }
    ]


def test_new_column_must_be_appended_to_preserve_physical_order() -> None:
    base = _table_model()
    target = copy.deepcopy(base)
    target_columns = target["schemas"][0]["tables"][0]["columns"]
    target_columns[0]["ordinal_position"] = 2
    target_columns.append(
        {
            "column_name": "Inserted First",
            "data_type": "text",
            "nullable": True,
            "ordinal_position": 1,
        }
    )

    plan = compile_migration_plan(base, target)

    assert plan["can_dry_run"] is False
    assert plan["statements"] == []
    assert plan["blockers"][0]["code"] == "column_order_change_unsupported"


def test_appended_columns_emit_in_target_ordinal_order_not_name_order() -> None:
    base = _table_model()
    target = copy.deepcopy(base)
    target["schemas"][0]["tables"][0]["columns"].extend(
        [
            {
                "column_name": "Zulu",
                "data_type": "text",
                "nullable": True,
                "ordinal_position": 2,
            },
            {
                "column_name": "Alpha",
                "data_type": "text",
                "nullable": True,
                "ordinal_position": 3,
            },
        ]
    )

    plan = compile_migration_plan(base, target)

    assert [item["target"] for item in plan["statements"]] == [
        'Sales Data.Order "Item".Zulu',
        'Sales Data.Order "Item".Alpha',
    ]


def test_appended_column_ordinal_gap_is_blocked() -> None:
    base = _table_model()
    target = copy.deepcopy(base)
    target["schemas"][0]["tables"][0]["columns"].append(
        {
            "column_name": "Gap",
            "data_type": "text",
            "nullable": True,
            "ordinal_position": 3,
        }
    )

    plan = compile_migration_plan(base, target)

    assert plan["statements"] == []
    assert plan["blockers"][0]["code"] == "column_order_change_unsupported"


def test_blocked_plan_retains_supported_deltas_as_review_only_proposals() -> None:
    base = _table_model(nullable=True, data_type="integer")
    base["schemas"][0]["tables"][0]["primary_key"] = None
    target = copy.deepcopy(base)
    target_table = target["schemas"][0]["tables"][0]
    target_table["comment"] = "blocked comment"
    target_table["columns"][0]["data_type"] = "bigint"
    target_table["columns"][0]["nullable"] = False

    plan = compile_migration_plan(base, target)

    assert plan["statements"] == []
    assert [item["kind"] for item in plan["proposed_statements"]] == [
        "alter_column_type",
        "set_not_null",
    ]
    assert plan["risk_summary"] == {"safe": 0, "warning": 1, "destructive": 1}
    assert plan["requires_destructive_confirmation"] is True


def test_primary_key_blocker_does_not_hide_an_independent_supported_delta() -> None:
    base = _table_model(nullable=False, data_type="integer")
    target = copy.deepcopy(base)
    target["schemas"][0]["tables"][0]["primary_key"] = None
    target["schemas"][0]["tables"][0]["columns"][0]["data_type"] = "bigint"

    plan = compile_migration_plan(base, target)

    assert plan["statements"] == []
    assert plan["blockers"][0]["code"] == "primary_key_change_unsupported"
    assert [item["kind"] for item in plan["proposed_statements"]] == [
        "alter_column_type"
    ]


def test_structured_object_refs_disambiguate_delimiter_bearing_identifiers() -> None:
    target = _empty_model()
    first_table = copy.deepcopy(_table_model()["schemas"][0]["tables"][0])
    first_table["table_name"] = "b.c"
    second_table = copy.deepcopy(first_table)
    second_table["table_name"] = "c"
    target["schemas"] = [
        {"schema_name": "a", "tables": [first_table]},
        {"schema_name": "a.b", "tables": [second_table]},
    ]

    plan = compile_migration_plan(_empty_model(), target)

    create_tables = [
        statement
        for statement in plan["statements"]
        if statement["kind"] == "create_table"
    ]
    assert [statement["target"] for statement in create_tables] == ["a.b.c", "a.b.c"]
    assert [statement["object_ref"] for statement in create_tables] == [
        {"schema_name": "a", "table_name": "b.c"},
        {"schema_name": "a.b", "table_name": "c"},
    ]
    assert [statement["dependency_refs"] for statement in create_tables] == [
        [{"schema_name": "a"}],
        [{"schema_name": "a.b"}],
    ]
