import pytest
from pydantic import ValidationError
from app.schemas import ApiKeyCreateIn, DiagramViewCreateIn, TableAnnotationUpsertIn

def test_api_key_create_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="Test\x00Key")

def test_diagram_view_create_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="Diagram\nView", layout_json={})

def test_table_annotation_upsert_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(schema_name="public\x0b", relation_name="test", body="test")

    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(schema_name="public", relation_name="test\x1b", body="test")
