from __future__ import annotations

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


@pytest.mark.parametrize("control_character", ["\x00", "\n", "\r", "\x1b", "\x7f"])
def test_diagram_view_name_rejects_ascii_control_characters(
    control_character: str,
) -> None:
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name=f"diagram{control_character}name", layout_json={})


@pytest.mark.parametrize("control_character", ["\x00", "\n", "\r", "\x1b", "\x7f"])
def test_table_annotation_identifiers_reject_ascii_control_characters(
    control_character: str,
) -> None:
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name=f"public{control_character}schema",
            relation_name="orders",
            body="annotation",
        )
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name="public",
            relation_name=f"orders{control_character}table",
            body="annotation",
        )


@pytest.mark.parametrize("control_character", ["\x00", "\n", "\r", "\x1b", "\x7f"])
def test_api_key_name_rejects_ascii_control_characters(
    control_character: str,
) -> None:
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name=f"operator{control_character}key")
