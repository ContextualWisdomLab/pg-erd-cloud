import pytest
from pydantic import ValidationError

from app.schemas import ApiKeyCreateIn, DiagramViewCreateIn, TableAnnotationUpsertIn


@pytest.mark.parametrize("control", ["\u0085", "\u009b"])
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


def test_single_line_fields_preserve_normal_unicode_and_multiline_body():
    view = DiagramViewCreateIn(name="고객_ERD_名前", layout_json={})
    annotation = TableAnnotationUpsertIn(
        schema_name="공용_schema",
        relation_name="注文_items",
        body="첫째 줄\nsecond line",
    )
    api_key = ApiKeyCreateIn(key_name="배포_キー")

    assert view.name == "고객_ERD_名前"
    assert annotation.body == "첫째 줄\nsecond line"
    assert api_key.key_name == "배포_キー"
