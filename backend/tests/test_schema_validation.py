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


_LOG_BREAKING_CHARACTERS = (
    [chr(code_point) for code_point in range(0x00, 0x20)]
    + [chr(code_point) for code_point in range(0x7F, 0xA0)]
    + ["\u2028", "\u2029"]
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


@pytest.mark.parametrize("code_point", _LOG_BREAKING_CHARACTERS)
def test_display_labels_reject_log_breaking_characters(code_point: str) -> None:
    """Reject C0, C1, DEL, and Unicode line separators in display labels."""
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name=f"diagram{code_point}name", layout_json={})
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name=f"api{code_point}key")


@pytest.mark.parametrize(
    "model_input",
    [
        {"name": "\u0085diagram", "layout_json": {}},
        {"name": "diagram\u2028name", "layout_json": {}},
        {"name": "diagram\u2029", "layout_json": {}},
    ],
)
def test_diagram_label_rejects_log_breaks_at_boundaries(model_input: dict) -> None:
    """Reject representative Unicode log breaks at each label position."""
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(**model_input)


def test_display_labels_accept_valid_unicode_and_bounds() -> None:
    """Preserve ordinary Unicode, spaces, emoji sequences, and length bounds."""
    DiagramViewCreateIn(name="valid space name", layout_json={})
    DiagramViewCreateIn(name="family 👨‍👩‍👧‍👦", layout_json={})
    DiagramViewCreateIn(name="unicode ë", layout_json={})
    DiagramViewCreateIn(name="a", layout_json={})
    DiagramViewCreateIn(name="a" * 200, layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="", layout_json={})
    with pytest.raises(ValidationError):
        DiagramViewCreateIn(name="a" * 201, layout_json={})

    ApiKeyCreateIn(key_name="valid space key")
    ApiKeyCreateIn(key_name="family 👨‍👩‍👧‍👦 key")
    ApiKeyCreateIn(key_name="unicode ë key")
    ApiKeyCreateIn(key_name="a")
    ApiKeyCreateIn(key_name="a" * 128)
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="")
    with pytest.raises(ValidationError):
        ApiKeyCreateIn(key_name="a" * 129)
