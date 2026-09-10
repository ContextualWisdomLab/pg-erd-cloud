"""Domain regressions for application labels versus PostgreSQL identifiers."""

import pytest
from pydantic import ValidationError

from app.schemas import ApiKeyCreateIn, DiagramViewCreateIn, TableAnnotationUpsertIn


def test_table_annotation_preserves_valid_quoted_identifier_characters() -> None:
    """Annotation keys must represent PostgreSQL identifiers, not UI labels."""
    annotation = TableAnnotationUpsertIn(
        schema_name="sales\narchive",
        relation_name="quarter\treport",
        body="Operational note",
    )

    assert annotation.schema_name == "sales\narchive"
    assert annotation.relation_name == "quarter\treport"


@pytest.mark.parametrize("field", ["schema_name", "relation_name"])
def test_table_annotation_rejects_nul_outside_postgresql_identifier_domain(field: str) -> None:
    """PostgreSQL quoted identifiers cannot contain code point zero."""
    payload = {
        "schema_name": "public",
        "relation_name": "orders",
        "body": "Operational note",
    }
    payload[field] = "unsafe\x00name"

    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(**payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (DiagramViewCreateIn, {"name": "view\nname", "layout_json": {}}),
        (ApiKeyCreateIn, {"key_name": "operator\nkey"}),
    ],
)
def test_application_owned_labels_reject_ascii_control_characters(model: type, payload: dict) -> None:
    """Human-facing application labels retain the control-character boundary."""
    with pytest.raises(ValidationError):
        model(**payload)
