from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ConnectionCreateIn, ProjectCreateIn, ProjectMemberAddIn


def test_project_name_length_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ProjectCreateIn(project_name="x" * 256)


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


@pytest.mark.parametrize("bad", ["My\x00Project", "line\nbreak", "tab\there", "del\x7f"])
def test_project_name_rejects_control_characters(bad: str) -> None:
    """Control chars in project names can enable XSS/injection when rendered."""
    with pytest.raises(ValidationError):
        ProjectCreateIn(project_name=bad)


def test_project_name_allows_spaces_and_unicode() -> None:
    """Spaces and printable unicode remain valid project names."""
    assert ProjectCreateIn(project_name="My ERD Project 프로젝트").project_name


@pytest.mark.parametrize("bad", ["prod\x00db", "conn\nname", "conn\rname", "x\x1f"])
def test_conn_name_rejects_control_characters(bad: str) -> None:
    """Control chars in connection names can enable XSS/injection when rendered."""
    with pytest.raises(ValidationError):
        ConnectionCreateIn(conn_name=bad, dsn="postgresql://localhost/db")


def test_conn_name_allows_spaces() -> None:
    """Printable connection names with spaces remain valid."""
    assert ConnectionCreateIn(
        conn_name="Prod Reader", dsn="postgresql://localhost/db"
    ).conn_name
