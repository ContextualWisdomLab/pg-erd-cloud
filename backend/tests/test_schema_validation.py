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


@pytest.mark.parametrize("control", ["\x00", "\t", "\n", "\r", "\x1b", "\x7f"])
def test_diagram_view_name_rejects_control_characters(control: str) -> None:
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name=f"운영{control}뷰", layout_json={})


@pytest.mark.parametrize("control", ["\x00", "\t", "\n", "\r", "\x1b", "\x7f"])
def test_api_key_name_rejects_control_characters(control: str) -> None:
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name=f"운영{control}키")


def test_new_name_boundaries_preserve_unicode_and_spaces() -> None:
    diagram = DiagramViewCreateIn(name="운영 ERD 日本語", layout_json={})
    api_key = ApiKeyCreateIn(key_name="운영 API 키")

    assert diagram.name == "운영 ERD 日本語"
    assert api_key.key_name == "운영 API 키"
