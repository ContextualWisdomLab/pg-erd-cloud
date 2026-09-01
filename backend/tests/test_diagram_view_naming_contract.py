"""Naming and compatibility contracts for the saved ERD diagram-view boundary."""

from app.models import DiagramView
from app.schemas import DiagramViewCreateIn, DiagramViewOut


def test_diagram_view_uses_specific_owned_name_with_legacy_wire_alias() -> None:
    """Keep internal/persisted naming specific while preserving the public `name` key."""
    assert "diagram_name" in DiagramView.__table__.columns
    assert "name" not in DiagramView.__table__.columns

    create_request = DiagramViewCreateIn(name="Architecture review")
    assert create_request.diagram_name == "Architecture review"
    assert "diagram_name" in DiagramViewCreateIn.model_fields
    assert "name" not in DiagramViewCreateIn.model_fields
    assert create_request.model_dump(by_alias=True)["name"] == "Architecture review"

    response = DiagramViewOut(
        diagram_view_uuid="00000000-0000-0000-0000-000000000001",
        diagram_name="Architecture review",
        created_at="2026-09-01T00:00:00Z",
        updated_at="2026-09-01T00:00:00Z",
    )
    assert response.diagram_name == "Architecture review"
    assert response.model_dump(by_alias=True)["name"] == "Architecture review"
