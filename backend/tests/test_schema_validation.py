from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ConnectionCreateIn, ProjectCreateIn, ProjectMemberAddIn


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

from app.schemas import ApiKeyCreateIn, DiagramViewCreateIn, TableAnnotationUpsertIn

def test_diagram_view_create_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="View\nNewline", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="View\x00Null", layout_json={})

def test_table_annotation_upsert_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name="schema\n", relation_name="valid_table", body="some body"
        )
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name="valid_schema", relation_name="table\x00", body="some body"
        )

def test_api_key_create_in_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="Key\nNewline")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="Key\x00Null")
