from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ApplySqlIn,
    ConnectionCreateIn,
    DbmlConvertIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
    TableAnnotationUpsertIn,
)


_ANNOTATION_NAME_FIELD_CASES = (
    ("schema_name", {"relation_name": "users", "body": "note"}),
    ("relation_name", {"schema_name": "public", "body": "note"}),
)


def test_project_name_length_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ProjectCreateIn(project_name="x" * 256)


def test_project_name_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        ProjectCreateIn(project_name="my\x00project")
    with pytest.raises(ValidationError):
        ProjectCreateIn(project_name="my\nproject")


def test_member_subject_rejects_control_or_whitespace() -> None:
    with pytest.raises(ValidationError):
        ProjectMemberAddIn(member_subject="dev:bad user", project_role="viewer")
    with pytest.raises(ValidationError):
        ProjectMemberAddIn(member_subject="dev:bad\x00user", project_role="viewer")


def test_connection_payload_lengths_are_bounded() -> None:
    with pytest.raises(ValidationError):
        ConnectionCreateIn(conn_name="x" * 129, dsn="postgresql://localhost/db")
    with pytest.raises(ValidationError):
        ConnectionCreateIn(conn_name="target", dsn="x" * 4097)


def test_conn_name_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        ConnectionCreateIn(conn_name="my\x00conn", dsn="postgresql://localhost/db")
    with pytest.raises(ValidationError):
        ConnectionCreateIn(conn_name="my\nconn", dsn="postgresql://localhost/db")


@pytest.mark.parametrize("field_name, extra", _ANNOTATION_NAME_FIELD_CASES)
@pytest.mark.parametrize("control", ("\x00", "\x09", "\x1f", "\x7f", "\r", "\n", "\x1b"))
def test_annotation_fields_reject_control_characters(field_name, extra, control) -> None:
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(**{field_name: f"safe{control}value", **extra})


@pytest.mark.parametrize("control", ("\x00", "\x0b", "\x0c", "\x1f", "\x7f", "\x1b"))
def test_annotation_body_rejects_non_whitespace_control_characters(control) -> None:
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name="public",
            relation_name="users",
            body=f"safe{control}value",
        )


def test_annotation_fields_allow_unicode_and_regular_spaces() -> None:
    TableAnnotationUpsertIn(
        schema_name="사용자 스키마",
        relation_name="주문 테이블",
        body="설명\t메모\n다음 줄",
    )


@pytest.mark.parametrize(
    "model, field_name, value",
    (
        (ApplySqlIn, "sql", "CREATE TABLE safe_table (id integer);"),
        (DbmlConvertIn, "dbml", "Table safe_table { id int [pk] }"),
    ),
)
@pytest.mark.parametrize("control", ("\x00", "\x0b", "\x0c", "\x1f", "\x7f"))
def test_sql_and_dbml_fields_reject_control_characters(model, field_name, value, control) -> None:
    with pytest.raises(ValidationError):
        model(**{field_name: f"{value}{control}"})
