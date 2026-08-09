from __future__ import annotations

import copy

import pytest

from app.forward.schema_model import (
    SchemaModelValidationError,
    canonicalize_schema_model,
    schema_model_digest,
)


def _model() -> dict:
    return {
        "format_version": 1,
        "postgresql_major": 18,
        "schemas": [
            {
                "schema_name": "Sales Data",
                "tables": [
                    {
                        "table_name": 'Order "Item"',
                        "comment": "Line items",
                        "columns": [
                            {
                                "column_name": "Description",
                                "data_type": "text",
                                "nullable": True,
                                "ordinal_position": 2,
                            },
                            {
                                "column_name": "Item ID",
                                "data_type": "bigint",
                                "nullable": False,
                                "ordinal_position": 1,
                            },
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


def test_canonical_model_preserves_identifier_semantics_and_column_order() -> None:
    model = _model()
    model["capture_id"] = "volatile"
    model["schemas"][0]["tables"][0]["relation_oid"] = 4242

    canonical = canonicalize_schema_model(model)

    table = canonical["schemas"][0]["tables"][0]
    assert table["table_name"] == 'Order "Item"'
    assert [column["column_name"] for column in table["columns"]] == [
        "Item ID",
        "Description",
    ]
    assert "capture_id" not in canonical
    assert "relation_oid" not in table


def test_digest_is_stable_across_object_order_and_volatile_metadata() -> None:
    left = _model()
    right = copy.deepcopy(left)
    right["captured_at"] = "2026-08-09T00:00:00Z"
    right["schemas"][0]["tables"][0]["relation_oid"] = 999
    right["schemas"].reverse()

    assert schema_model_digest(left) == schema_model_digest(right)


def test_missing_and_null_column_comments_have_one_canonical_form() -> None:
    without_comment = _model()
    with_null_comment = copy.deepcopy(without_comment)
    with_null_comment["schemas"][0]["tables"][0]["columns"][0]["comment"] = None

    canonical = canonicalize_schema_model(without_comment)

    assert all(
        "comment" in column
        for column in canonical["schemas"][0]["tables"][0]["columns"]
    )
    assert schema_model_digest(without_comment) == schema_model_digest(with_null_comment)


@pytest.mark.parametrize(
    ("input_type", "canonical_type"),
    [
        ("INT", "integer"),
        ("BOOL[]", "boolean[]"),
        ("VarChar(32)", "character varying(32)"),
        ("CHAR", "character(1)"),
        ("DECIMAL(10, 2)", "numeric(10,2)"),
        ("timestamp", "timestamp without time zone"),
        ("TIME(3)", "time(3) without time zone"),
    ],
)
def test_data_types_canonicalize_to_postgresql_catalog_spelling(
    input_type: str, canonical_type: str
) -> None:
    model = _model()
    model["schemas"][0]["tables"][0]["columns"][0]["data_type"] = input_type

    canonical = canonicalize_schema_model(model)

    columns = canonical["schemas"][0]["tables"][0]["columns"]
    assert next(
        column["data_type"]
        for column in columns
        if column["column_name"] == "Description"
    ) == canonical_type


@pytest.mark.parametrize("pseudo_type", ["smallserial", "serial", "bigserial", "serial[]"])
def test_serial_pseudo_types_are_rejected_as_non_convergent(pseudo_type: str) -> None:
    model = _model()
    model["schemas"][0]["tables"][0]["columns"][0]["data_type"] = pseudo_type

    with pytest.raises(SchemaModelValidationError, match="serial pseudo-type"):
        canonicalize_schema_model(model)


def test_primary_key_columns_must_be_explicitly_not_nullable() -> None:
    model = _model()
    item_id = model["schemas"][0]["tables"][0]["columns"][1]
    item_id["nullable"] = True

    with pytest.raises(SchemaModelValidationError, match="primary_key.*not nullable"):
        canonicalize_schema_model(model)


def test_digest_changes_for_compiler_relevant_mutation() -> None:
    before = _model()
    after = copy.deepcopy(before)
    after["schemas"][0]["tables"][0]["columns"][0]["nullable"] = False

    assert schema_model_digest(before) != schema_model_digest(after)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda model: model["schemas"][0]["tables"][0].update(
                {"unsupported_features": ["row_security"]}
            ),
            "unsupported feature",
        ),
        (
            lambda model: model["schemas"][0]["tables"][0]["columns"].append(
                {
                    "column_name": "Item ID",
                    "data_type": "integer",
                    "nullable": False,
                    "ordinal_position": 3,
                }
            ),
            "duplicate column",
        ),
        (
            lambda model: model["schemas"][0]["tables"][0]["primary_key"].update(
                {"columns": ["missing_column"]}
            ),
            "unknown column",
        ),
        (
            lambda model: model["schemas"][0].update({"schema_name": "bad\x00name"}),
            "NUL",
        ),
        (
            lambda model: model.update({"format_version": 2}),
            "format_version",
        ),
        (
            lambda model: model["schemas"][0]["tables"][0]["columns"][0].update(
                {"data_type": "text); DROP TABLE audit_log; --"}
            ),
            "unsupported data type",
        ),
        (
            lambda model: model["schemas"][0]["tables"][0]["columns"][0].update(
                {"default": "0); DROP TABLE audit_log; --"}
            ),
            "default expressions",
        ),
    ],
)
def test_model_validation_fails_closed(mutate, message: str) -> None:
    model = _model()
    mutate(model)

    with pytest.raises(SchemaModelValidationError, match=message):
        canonicalize_schema_model(model)


def test_model_rejects_unrecognized_fields_in_authoritative_objects() -> None:
    model = _model()
    model["schemas"][0]["tables"][0]["mystery_sql"] = "DROP DATABASE production"

    with pytest.raises(SchemaModelValidationError, match="unrecognized field"):
        canonicalize_schema_model(model)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([], "model must be an object"),
        ({"format_version": 1, "postgresql_major": 18, "schemas": {}}, "schemas must be a list"),
        ({"format_version": 1, "postgresql_major": 13, "schemas": []}, "supported version"),
        ({"format_version": 1, "postgresql_major": True, "schemas": []}, "supported version"),
        ({"format_version": 1, "postgresql_major": 18, "schemas": [1]}, "must be an object"),
    ],
)
def test_root_shape_validation(value, message: str) -> None:
    with pytest.raises(SchemaModelValidationError, match=message):
        canonicalize_schema_model(value)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda model: model["schemas"][0].update({"schema_name": 1}), "must be text"),
        (lambda model: model["schemas"][0].update({"schema_name": ""}), "must not be empty"),
        (lambda model: model["schemas"][0].update({"schema_name": "가" * 22}), "63-byte"),
        (lambda model: model["schemas"][0].update({"tables": {}}), "tables must be a list"),
        (lambda model: model["schemas"][0]["tables"].append(1), "must be an object"),
        (lambda model: model["schemas"][0]["tables"][0].update({"comment": 1}), "text or null"),
        (lambda model: model["schemas"][0]["tables"][0].update({"comment": "bad\x00comment"}), "NUL"),
        (lambda model: model["schemas"][0]["tables"][0].update({"columns": {}}), "columns must be a list"),
        (lambda model: model["schemas"][0]["tables"][0]["columns"].append(1), "must be an object"),
        (lambda model: model["schemas"][0]["tables"][0]["columns"][0].update({"nullable": 1}), "must be boolean"),
        (lambda model: model["schemas"][0]["tables"][0]["columns"][0].update({"ordinal_position": 0}), "positive integer"),
        (lambda model: model["schemas"][0]["tables"][0]["columns"][0].update({"comment": 1}), "text or null"),
        (lambda model: model["schemas"][0]["tables"][0]["columns"][0].update({"comment": "bad\x00comment"}), "NUL"),
        (lambda model: model["schemas"][0]["tables"][0]["primary_key"].update({"columns": []}), "must not be empty"),
        (lambda model: model["schemas"][0]["tables"][0]["primary_key"].update({"columns": ["Item ID", "Item ID"]}), "duplicate column"),
        (lambda model: model["schemas"][0]["tables"][0]["primary_key"].update({"deferrable": 1}), "must be boolean"),
        (
            lambda model: model["schemas"][0]["tables"][0]["primary_key"].update(
                {"deferrable": False, "initially_deferred": True}
            ),
            "initially_deferred requires deferrable",
        ),
        (lambda model: model["schemas"][0]["tables"][0]["columns"][0].update({"ordinal_position": 1}), "duplicate column ordinal"),
        (lambda model: model["schemas"][0]["tables"][0].update({"indexes": [{}]}), "unsupported feature"),
    ],
)
def test_nested_shape_validation(mutate, message: str) -> None:
    model = _model()
    mutate(model)
    with pytest.raises(SchemaModelValidationError, match=message):
        canonicalize_schema_model(model)


def test_duplicate_schema_and_table_are_rejected() -> None:
    model = _model()
    model["schemas"].append(copy.deepcopy(model["schemas"][0]))
    with pytest.raises(SchemaModelValidationError, match="duplicate schema"):
        canonicalize_schema_model(model)

    model = _model()
    model["schemas"][0]["tables"].append(
        copy.deepcopy(model["schemas"][0]["tables"][0])
    )
    with pytest.raises(SchemaModelValidationError, match="duplicate table"):
        canonicalize_schema_model(model)
