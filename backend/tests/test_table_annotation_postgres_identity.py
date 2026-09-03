from __future__ import annotations


from app.schemas import TableAnnotationUpsertIn


def test_table_annotation_preserves_postgres_quoted_identifiers() -> None:
    # PostgreSQL allows any character except NUL in quoted identifiers.
    # We must allow LF, TAB, etc.
    valid_schema = "my\nschema\tname"
    valid_relation = "my\nrelation\tname"
    body = "Test body"

    # Should not raise ValidationError
    annotation = TableAnnotationUpsertIn(
        schema_name=valid_schema,
        relation_name=valid_relation,
        body=body,
    )

    assert annotation.schema_name == valid_schema
    assert annotation.relation_name == valid_relation
