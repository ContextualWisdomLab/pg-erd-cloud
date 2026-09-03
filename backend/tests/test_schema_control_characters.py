from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas import ApiKeyCreateIn, DiagramViewCreateIn, TableAnnotationUpsertIn


@pytest.mark.parametrize(
    ("model_cls", "field_name", "other_fields"),
    [
        (DiagramViewCreateIn, "name", {"layout_json": {}}),
        (ApiKeyCreateIn, "key_name", {}),
    ],
)
@pytest.mark.parametrize("control", ["\x00", "\n", "\r", "\t", "\x1b", "\x7f"])
def test_product_label_fields_reject_ascii_control_characters(
    model_cls: type[BaseModel],
    field_name: str,
    other_fields: dict[str, object],
    control: str,
) -> None:
    payload = {**other_fields, field_name: f"safe{control}name"}

    with pytest.raises(ValidationError):
        model_cls.model_validate(payload)


def test_table_annotation_body_keeps_multiline_content() -> None:
    body = "First line\nSecond line\twith indentation"

    annotation = TableAnnotationUpsertIn(
        schema_name="public",
        relation_name="orders",
        body=body,
    )

    assert annotation.body == body
