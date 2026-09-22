import pytest
from pydantic import ValidationError

from app.schemas import (
    ApiKeyCreateIn,
    ConnectionCreateIn,
    DiagramViewCreateIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
    TableAnnotationUpsertIn,
)


@pytest.mark.parametrize("control", ["\n", "\x1b", "\x7f", "\u0085", "\u009b"])
@pytest.mark.parametrize(
    ("model", "field_name", "base_values"),
    [
        (ProjectCreateIn, "project_name", {}),
        (ProjectMemberAddIn, "member_subject", {}),
        (ConnectionCreateIn, "conn_name", {"dsn": "postgresql://db/app"}),
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
def test_single_line_fields_reject_control_characters(
    control, model, field_name, base_values
):
    values = dict(base_values)
    values[field_name] = f"safe{control}injected"

    with pytest.raises(ValidationError):
        model(**values)


def test_single_line_fields_preserve_normal_unicode_and_multiline_body():
    project = ProjectCreateIn(project_name="고객_ERD_名前")
    member = ProjectMemberAddIn(member_subject="dev:성호")
    connection = ConnectionCreateIn(
        conn_name="분석_DB_名前", dsn="postgresql://db/app"
    )
    view = DiagramViewCreateIn(name="고객_ERD_名前", layout_json={})
    annotation = TableAnnotationUpsertIn(
        schema_name="공용_schema",
        relation_name="注文_items",
        body="첫째 줄\nsecond line",
    )
    api_key = ApiKeyCreateIn(key_name="배포_キー")

    assert project.project_name == "고객_ERD_名前"
    assert member.member_subject == "dev:성호"
    assert connection.conn_name == "분석_DB_名前"
    assert view.name == "고객_ERD_名前"
    assert annotation.body == "첫째 줄\nsecond line"
    assert api_key.key_name == "배포_キー"
