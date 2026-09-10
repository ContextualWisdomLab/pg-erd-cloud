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


@pytest.mark.parametrize(
    "control",
    [
        *(chr(code_point) for code_point in range(0x00, 0x20)),
        chr(0x7F),
        *(chr(code_point) for code_point in range(0x80, 0xA0)),
        "\u2028",
        "\u2029",
    ],
)
@pytest.mark.parametrize("placement", ["prefix", "middle", "suffix"])
def test_dsn_rejects_non_text_controls_at_every_position(
    control: str, placement: str
) -> None:
    if placement == "prefix":
        dsn = f"{control}postgresql://localhost/db"
    elif placement == "middle":
        dsn = f"postgresql://local{control}host/db"
    else:
        dsn = f"postgresql://localhost/db{control}"

    with pytest.raises(ValidationError):
        ConnectionCreateIn(conn_name="target", dsn=dsn)


def test_dsn_preserves_printable_unicode_and_encoded_credentials() -> None:
    body = ConnectionCreateIn(
        conn_name="target",
        dsn="postgresql://사용자:%E2%9C%93%20secret@db.example/データベース",
    )

    assert body.dsn == "postgresql://사용자:%E2%9C%93%20secret@db.example/データベース"
