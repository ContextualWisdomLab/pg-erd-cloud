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


@pytest.mark.parametrize("control", ["\u0085", "\u009b"])
def test_project_name_rejects_c1_control_characters(control: str) -> None:
    """프로젝트 이름은 로그·감사 출력을 교란할 수 있는 C1 제어문자를 거부한다."""
    with pytest.raises(ValidationError):
        ProjectCreateIn(project_name=f"my{control}project")


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


@pytest.mark.parametrize("control", ["\u0085", "\u009b"])
def test_conn_name_rejects_c1_control_characters(control: str) -> None:
    """연결 이름은 로그·감사 출력을 교란할 수 있는 C1 제어문자를 거부한다."""
    with pytest.raises(ValidationError):
        ConnectionCreateIn(
            conn_name=f"my{control}conn",
            dsn="postgresql://localhost/db",
        )
