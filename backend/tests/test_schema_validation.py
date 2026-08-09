from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ApplySqlIn,
    ConnectionCreateIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
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


def test_apply_sql_preserves_multiline_unicode_transport_characters() -> None:
    sql = 'CREATE TABLE "注文" (\n\t"識別子" text\r\n);'

    assert ApplySqlIn(sql=sql).sql == sql


@pytest.mark.parametrize(
    "codepoint",
    [*range(0x00, 0x09), 0x0B, 0x0C, *range(0x0E, 0x20), 0x7F],
)
@pytest.mark.parametrize("position", ["beginning", "middle", "end"])
def test_apply_sql_rejects_non_text_controls_at_every_position(
    codepoint: int, position: str
) -> None:
    control = chr(codepoint)
    safe_sql = "CREATE TABLE audit_record (secret_token text);"
    values = {
        "beginning": control + safe_sql,
        "middle": safe_sql[:20] + control + safe_sql[20:],
        "end": safe_sql + control,
    }

    with pytest.raises(ValidationError, match="disallowed control character"):
        ApplySqlIn(sql=values[position])
