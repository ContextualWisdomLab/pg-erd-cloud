"""Regression tests for log-safe user-controlled identifiers."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas import (
    ApiKeyCreateIn,
    ConnectionCreateIn,
    DiagramViewCreateIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
    TableAnnotationUpsertIn,
)


_LOG_BREAKING_CHARACTERS = (
    tuple(chr(code_point) for code_point in range(0x20))
    + tuple(chr(code_point) for code_point in range(0x7F, 0xA0))
    + ("\u2028", "\u2029")
)


def _place_character(character: str, position: str) -> str:
    """Place a hostile character at a representative string boundary."""

    if position == "prefix":
        return f"{character}label"
    if position == "middle":
        return f"la{character}bel"
    if position == "suffix":
        return f"label{character}"
    raise AssertionError(f"unexpected position: {position}")


def _model_builders(value: str) -> tuple[Callable[[], BaseModel], ...]:
    """Build every request model containing a log-sensitive identifier."""

    return (
        lambda: ProjectCreateIn(project_name=value),
        lambda: ProjectMemberAddIn(
            member_subject=f"dev:{value}",
            project_role="viewer",
        ),
        lambda: ConnectionCreateIn(
            conn_name=value,
            dsn="postgresql://localhost/database_name",
        ),
        lambda: DiagramViewCreateIn(name=value, layout_json={}),
        lambda: TableAnnotationUpsertIn(
            schema_name=value,
            relation_name="safe_relation",
            body="annotation body",
        ),
        lambda: TableAnnotationUpsertIn(
            schema_name="safe_schema",
            relation_name=value,
            body="annotation body",
        ),
        lambda: ApiKeyCreateIn(key_name=value),
    )


@pytest.mark.parametrize("character", _LOG_BREAKING_CHARACTERS)
@pytest.mark.parametrize("position", ["prefix", "middle", "suffix"])
def test_identifier_models_reject_every_log_breaking_character(
    character: str,
    position: str,
) -> None:
    """Reject C0, DEL, C1, and Unicode line separators everywhere."""

    value = _place_character(character, position)
    for build_model in _model_builders(value):
        with pytest.raises(ValidationError):
            build_model()


def test_identifier_models_preserve_valid_multilingual_text() -> None:
    """Preserve exact multilingual labels, ordinary spaces, and emoji."""

    project = ProjectCreateIn(project_name="고객 프로젝트 🚀")
    member = ProjectMemberAddIn(
        member_subject="dev:사용자",
        project_role="editor",
    )
    connection = ConnectionCreateIn(
        conn_name="분석 연결 🚀",
        dsn="postgresql://localhost/database_name",
    )
    diagram = DiagramViewCreateIn(name="운영 ERD 🚀", layout_json={})
    annotation = TableAnnotationUpsertIn(
        schema_name="운영 스키마",
        relation_name="고객 주문",
        body="본문은\n여러 줄을 유지합니다.",
    )
    api_key = ApiKeyCreateIn(key_name="운영 키 🚀")

    assert project.project_name == "고객 프로젝트 🚀"
    assert member.member_subject == "dev:사용자"
    assert connection.conn_name == "분석 연결 🚀"
    assert diagram.name == "운영 ERD 🚀"
    assert annotation.schema_name == "운영 스키마"
    assert annotation.relation_name == "고객 주문"
    assert api_key.key_name == "운영 키 🚀"


def test_member_subject_still_rejects_visible_whitespace() -> None:
    """Preserve the existing no-whitespace identity-subject contract."""

    with pytest.raises(ValidationError):
        ProjectMemberAddIn(
            member_subject="dev:bad user",
            project_role="viewer",
        )
