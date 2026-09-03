from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import TableAnnotationUpsertIn


def test_table_annotation_preserves_postgres_quoted_identifiers() -> None:
    valid_schema = "my\nschema\tname"
    valid_relation = "my\nrelation\tname"
    body = "Test body"

    annotation = TableAnnotationUpsertIn(
        schema_name=valid_schema,
        relation_name=valid_relation,
        body=body,
    )

    assert annotation.schema_name == valid_schema
    assert annotation.relation_name == valid_relation


@pytest.mark.parametrize("field_name", ["schema_name", "relation_name"])
def test_table_annotation_rejects_postgres_nul_identifier(field_name: str) -> None:
    payload = {
        "schema_name": "public",
        "relation_name": "orders",
        "body": "Test body",
    }
    payload[field_name] = "invalid\x00identifier"

    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn.model_validate(payload)
