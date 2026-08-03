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


@pytest.mark.parametrize(
    "valid_input",
    [
        "Valid Name",
        "한글 이름",
        "データベース",
        "🚀 Project",
        "name_with_underscores",
        "name-with-dashes",
    ],
)
def test_hardened_pydantic_strings_accept_valid_input(valid_input: str) -> None:
    DiagramViewCreateIn(name=valid_input, layout_json={})
    TableAnnotationUpsertIn(
        schema_name=valid_input, relation_name=valid_input, body="body"
    )
    ApiKeyCreateIn(key_name=valid_input)


@pytest.mark.parametrize(
    "control_char",
    [chr(i) for i in range(32)] + [chr(127)],
)
@pytest.mark.parametrize(
    "position_fmt",
    ["{}suffix", "pre{}post", "prefix{}"],
)
def test_hardened_pydantic_strings_reject_control_characters(
    control_char: str, position_fmt: str
) -> None:
    test_str = position_fmt.format(control_char)

    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name=test_str, layout_json={})

    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name=test_str, relation_name="valid", body="body"
        )

    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name="valid", relation_name=test_str, body="body"
        )

    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name=test_str)


def test_table_annotation_body_allows_multiline() -> None:
    """Ensure the body field is untouched by the strict validation."""
    multiline_body = "Line 1\nLine 2\r\nLine 3\t(with tab)"
    TableAnnotationUpsertIn(
        schema_name="public",
        relation_name="users",
        body=multiline_body,
    )
