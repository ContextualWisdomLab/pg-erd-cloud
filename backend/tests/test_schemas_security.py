import pytest
from pydantic import ValidationError
from app.schemas import DiagramViewCreateIn, TableAnnotationUpsertIn, ApiKeyCreateIn

def test_control_character_rejection():
    # DiagramViewCreateIn
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="test\x00", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="test\n", layout_json={})
    DiagramViewCreateIn(name="valid name", layout_json={})

    # TableAnnotationUpsertIn
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(schema_name="public\x00", relation_name="users", body="test")
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(schema_name="public", relation_name="users\n", body="test")
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(schema_name="public", relation_name="users", body="test\x00")
    TableAnnotationUpsertIn(schema_name="public", relation_name="users", body="valid body\nwith newlines")

    # ApiKeyCreateIn
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="test\x00")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="test\n")
    ApiKeyCreateIn(key_name="valid name")
