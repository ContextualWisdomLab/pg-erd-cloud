import pytest
from pydantic import ValidationError

from app.schemas import ApiKeyCreateIn, DiagramViewCreateIn, TableAnnotationUpsertIn


def test_postgresql_source_identifiers_preserve_non_nul_controls() -> None:
    payload = TableAnnotationUpsertIn(
        schema_name="audit\x01trail",
        relation_name="line\x7fitem",
        body="operator note",
    )

    assert payload.schema_name == "audit\x01trail"
    assert payload.relation_name == "line\x7fitem"


def test_postgresql_source_identifiers_reject_nul() -> None:
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name="audit\x00trail",
            relation_name="orders",
            body="operator note",
        )


def test_product_owned_labels_reject_control_characters() -> None:
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="Finance\nView", layout_json={})

    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="nightly\tkey")
