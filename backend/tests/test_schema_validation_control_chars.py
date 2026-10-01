import pytest
from pydantic import ValidationError
from app.schemas import ApiKeyCreateIn, DiagramViewCreateIn, TableAnnotationUpsertIn

def test_api_key_create_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="Test\x00Key")

def test_diagram_view_create_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="Diagram\nView", layout_json={})


def test_table_annotation_identifiers_reject_only_nul() -> None:
    """PostgreSQL quoted identifiers retain controls other than NUL."""
    for identifier in ("public\x0b", "test\x1b", "quoted\x7f"):
        parsed = TableAnnotationUpsertIn(
            schema_name=identifier,
            relation_name=identifier,
            body="test",
        )
        assert parsed.schema_name == identifier
        assert parsed.relation_name == identifier

    for field_name in ("schema_name", "relation_name"):
        payload = {
            "schema_name": "public",
            "relation_name": "table_name",
            "body": "test",
            field_name: "bad\x00identifier",
        }
        with pytest.raises(ValidationError):
            TableAnnotationUpsertIn(**payload)
