from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ConnectionCreateIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
    TableAnnotationUpsertIn,
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


def test_annotation_identifiers_preserve_postgresql_quoted_identifier_bytes() -> None:
    model = TableAnnotationUpsertIn(
        schema_name="reporting\t2026",
        relation_name="orders\narchive",
        body="annotation",
    )

    assert model.schema_name == "reporting\t2026"
    assert model.relation_name == "orders\narchive"


def test_annotation_identifiers_reject_nul() -> None:
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name="reporting\x00archive",
            relation_name="orders",
            body="annotation",
        )
    with pytest.raises(ValidationError):
        TableAnnotationUpsertIn(
            schema_name="reporting",
            relation_name="orders\x00archive",
            body="annotation",
        )
