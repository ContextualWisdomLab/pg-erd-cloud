import pytest
from pydantic import ValidationError
from app.schemas import ApiKeyCreateIn, DiagramViewCreateIn, TableAnnotationUpsertIn

def test_api_key_create_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="Test\x00Key")

def test_diagram_view_create_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="Diagram\nView", layout_json={})
