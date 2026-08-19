from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ApiKeyCreateIn,
    ApplySqlIn,
    ConnectionCreateIn,
    DiagramViewCreateIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
    TableAnnotationUpsertIn,
)


_NAMED_FIELD_CASES = (
    (DiagramViewCreateIn, "name", {"layout_json": {}}),
    (TableAnnotationUpsertIn, "schema_name", {"relation_name": "users", "body": "note"}),
    (TableAnnotationUpsertIn, "relation_name", {"schema_name": "public", "body": "note"}),
    (ApiKeyCreateIn, "key_name", {}),
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


@pytest.mark.parametrize("model, field_name, extra", _NAMED_FIELD_CASES)
@pytest.mark.parametrize("control", ("\x00", "\x09", "\x1f", "\x7f", "\r", "\n", "\x1b"))
def test_named_schema_fields_reject_control_characters(model, field_name, extra, control) -> None:
    with pytest.raises(ValidationError):
        model(**{field_name: f"safe{control}value", **extra})


@pytest.mark.parametrize("model, field_name, extra", _NAMED_FIELD_CASES)
def test_named_schema_fields_allow_unicode_and_regular_spaces(model, field_name, extra) -> None:
    model(**{field_name: "사용자 이름", **extra})


def test_apply_sql_accepts_supported_ddl_batch_and_rejects_other_sql() -> None:
    ApplySqlIn(
        sql=(
            "CREATE TABLE safe_table (id integer); "
            "ALTER TABLE safe_table ADD COLUMN created_at integer; "
            "CREATE INDEX idx_safe ON safe_table (id);"
        )
    )
    for sql in (
        "SELECT 1;",
        "DROP TABLE safe_table;",
        "-- comment\nCREATE TABLE safe_table (id integer);",
        'CREATE TABLE "safe_table" (id integer);',
    ):
        with pytest.raises(ValidationError):
            ApplySqlIn(sql=sql)
