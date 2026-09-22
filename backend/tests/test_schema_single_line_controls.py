import pytest
from pydantic import ValidationError

from app.schemas import (
    ApiKeyCreateIn,
    DiagramViewCreateIn,
    TableAnnotationUpsertIn,
)

@pytest.mark.parametrize("control", ["\x85", "\x9b"])
@pytest.mark.parametrize(
    ("model", "field_name", "base_values"),
    [
        (DiagramViewCreateIn, "name", {"layout_json": {}}),
        (
            TableAnnotationUpsertIn,
            "schema_name",
            {"relation_name": "orders", "body": "line 1\nline 2"},
        ),
        (
            TableAnnotationUpsertIn,
            "relation_name",
            {"schema_name": "public", "body": "line 1\nline 2"},
        ),
        (ApiKeyCreateIn, "key_name", {}),
    ],
)
def test_single_line_fields_reject_c1_controls(
    control, model, field_name, base_values
):
    values = dict(base_values)
    values[field_name] = f"safe{control}injected"

    with pytest.raises(ValidationError):
        model(**values)
