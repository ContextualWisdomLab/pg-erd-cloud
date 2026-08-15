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

from app.schemas import DiagramViewCreateIn, ApiKeyCreateIn

def test_identifier_rejects_control_characters() -> None:
    # Test DiagramViewCreateIn.name
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="test\x00", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="test\n", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="test\r", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="test\x1f", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="\x7ftest", layout_json={})

    # Test valid DiagramViewCreateIn.name
    DiagramViewCreateIn(name="valid space name", layout_json={})
    DiagramViewCreateIn(name="emoji 🚀", layout_json={})
    DiagramViewCreateIn(name="unicode ë", layout_json={})

    # Test ApiKeyCreateIn.key_name
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="test\x00")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="test\n")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="test\r")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="test\x1f")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="\x7ftest")

    # Test valid ApiKeyCreateIn.key_name
    ApiKeyCreateIn(key_name="valid space key")
    ApiKeyCreateIn(key_name="emoji 🚀 key")
    ApiKeyCreateIn(key_name="unicode ë key")
