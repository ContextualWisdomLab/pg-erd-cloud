from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ApiKeyCreateIn,
    ApplySqlIn,
    ConnectionCreateIn,
    DbmlConvertIn,
    DiagramViewCreateIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
    TableAnnotationUpsertIn,
)


_C1_FIELD_CASES = (
    (ProjectCreateIn, "project_name", {"project_name": "safe"}),
    (
        ProjectMemberAddIn,
        "member_subject",
        {"member_subject": "dev:safe", "project_role": "viewer"},
    ),
    (
        ConnectionCreateIn,
        "conn_name",
        {"conn_name": "safe", "dsn": "postgresql://localhost/db"},
    ),
    (ConnectionCreateIn, "dsn", {"conn_name": "safe", "dsn": "postgresql://localhost/db"}),
    (ApplySqlIn, "sql", {"sql": "CREATE TABLE safe_table (id integer);"}),
    (DiagramViewCreateIn, "name", {"name": "safe", "layout_json": {}}),
    (
        TableAnnotationUpsertIn,
        "schema_name",
        {"schema_name": "public", "relation_name": "users", "body": "note"},
    ),
    (
        TableAnnotationUpsertIn,
        "relation_name",
        {"schema_name": "public", "relation_name": "users", "body": "note"},
    ),
    (
        TableAnnotationUpsertIn,
        "body",
        {"schema_name": "public", "relation_name": "users", "body": "note"},
    ),
    (DbmlConvertIn, "dbml", {"dbml": "Table safe_table { id int }"}),
    (ApiKeyCreateIn, "key_name", {"key_name": "safe"}),
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


@pytest.mark.parametrize(
    "sql",
    (
        "DROP TABLE users;",
        "CREATE TABLE safe_table (id bigint); DROP TABLE users;",
        'CREATE TABLE "unsafe_table" (id bigint);',
    ),
)
def test_apply_sql_rejects_non_allowlisted_statements(sql: str) -> None:
    """The request model must reject SQL before the execution layer runs."""

    with pytest.raises(ValidationError):
        ApplySqlIn(sql=sql)


@pytest.mark.parametrize("model, field_name, payload", _C1_FIELD_CASES)
@pytest.mark.parametrize("control", ("\x80", "\x9f"))
def test_schema_fields_reject_unicode_c1_controls(model, field_name, payload, control) -> None:
    """Reject C1 controls on every user-controlled text boundary in the models."""

    invalid = {**payload, field_name: f"{payload[field_name]}{control}"}
    with pytest.raises(ValidationError):
        model(**invalid)
