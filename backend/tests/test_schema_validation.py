from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ApiKeyCreateIn,
    ConnectionCreateIn,
    DiagramViewCreateIn,
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


@pytest.mark.parametrize(
    "code_point",
    [chr(i) for i in range(32)] + ["\x7f"],
)
def test_identifier_rejects_all_control_characters(code_point: str) -> None:
    # Test DiagramViewCreateIn.name at start, middle, and end
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name=f"{code_point}test", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name=f"te{code_point}st", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name=f"test{code_point}", layout_json={})

    # Test ApiKeyCreateIn.key_name at start, middle, and end
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name=f"{code_point}test")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name=f"te{code_point}st")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name=f"test{code_point}")


def test_identifier_accepts_valid_characters_and_bounds() -> None:
    # Valid DiagramViewCreateIn.name
    DiagramViewCreateIn(name="valid space name", layout_json={})
    DiagramViewCreateIn(name="emoji 🚀", layout_json={})
    DiagramViewCreateIn(name="unicode ë", layout_json={})
    DiagramViewCreateIn(name="a", layout_json={})  # Min length
    DiagramViewCreateIn(name="a" * 200, layout_json={})  # Max length
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="a" * 201, layout_json={})

    # Valid ApiKeyCreateIn.key_name
    ApiKeyCreateIn(key_name="valid space key")
    ApiKeyCreateIn(key_name="emoji 🚀 key")
    ApiKeyCreateIn(key_name="unicode ë key")
    ApiKeyCreateIn(key_name="a")  # Min length
    ApiKeyCreateIn(key_name="a" * 128)  # Max length
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="a" * 129)
