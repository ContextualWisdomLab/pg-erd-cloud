from __future__ import annotations

from app.pg_introspect.column_examples import (
    add_column_examples,
    infer_column_example,
)


def test_infer_column_example_uses_name_and_type_hints() -> None:
    assert (
        infer_column_example(
            {
                "column_name": "customer_email",
                "data_type": "character varying",
                "type_name": "varchar",
            }
        )
        == "user@example.com"
    )
    assert (
        infer_column_example(
            {
                "column_name": "order_id",
                "data_type": "bigint",
                "type_name": "int8",
            }
        )
        == "1001"
    )
    assert (
        infer_column_example(
            {
                "column_name": "tenant_uuid",
                "data_type": "text",
                "type_name": "text",
            }
        )
        == "550e8400-e29b-41d4-a716-446655440000"
    )
    assert (
        infer_column_example(
            {
                "column_name": "created_at",
                "data_type": "timestamp with time zone",
                "type_name": "timestamptz",
            }
        )
        == "2026-01-15T09:30:00Z"
    )


def test_add_column_examples_preserves_existing_fields() -> None:
    columns = [
        {
            "column_name": "status",
            "data_type": "text",
            "column_comment": "Current workflow state",
        }
    ]

    # The in-place modification changes the original dict,
    # which is intended behavior since these dicts are freshly instantiated
    enriched = add_column_examples(columns)

    assert enriched[0]["column_comment"] == "Current workflow state"
    assert enriched[0]["example_value"] == "active"
    assert enriched[0]["example_value_source"] == "generated"
