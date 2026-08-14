from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ApplySqlIn,
    ConnectionCreateIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
)


_FORBIDDEN_SQL_CONTROLS = tuple(
    chr(codepoint)
    for codepoint in (*range(0x00, 0x09), 0x0B, 0x0C, *range(0x0E, 0x20), 0x7F)
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


@pytest.mark.parametrize("control", _FORBIDDEN_SQL_CONTROLS)
@pytest.mark.parametrize("position", ("start", "middle", "end"))
def test_apply_sql_rejects_non_text_controls(control: str, position: str) -> None:
    """Reject every forbidden SQL control at every payload boundary position."""
    fragments = {
        "start": f"{control}CREATE TABLE safe_table (id bigint);",
        "middle": f"CREATE TABLE safe{control}_table (id bigint);",
        "end": f"CREATE TABLE safe_table (id bigint);{control}",
    }

    with pytest.raises(ValidationError):
        ApplySqlIn(sql=fragments[position])


def test_apply_sql_accepts_multiline_text_and_unicode() -> None:
    """Preserve tabs, line endings, Unicode, and printable SQL text."""
    sql = (
        "CREATE TABLE 사용자 (\r\n"
        "\tid bigint,\n"
        "\t설명 text DEFAULT '공백 ; -- 그대로'\r\n"
        ");"
    )

    assert ApplySqlIn(sql=sql).sql == sql


def test_apply_sql_validation_error_does_not_echo_secret_sql() -> None:
    """Keep rejected SQL content out of validation error representations."""
    secret = "never-log-this-token"

    with pytest.raises(ValidationError) as caught:
        ApplySqlIn(sql=f"CREATE TABLE safe_table (value text DEFAULT '{secret}\x00');")

    assert secret not in str(caught.value)
    assert secret not in repr(caught.value.errors(include_url=False))
