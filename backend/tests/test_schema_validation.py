from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ConnectionCreateIn,
    MigrationRunCancelIn,
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


def test_deployer_is_an_assignable_non_owner_role() -> None:
    payload = ProjectMemberAddIn(
        member_subject="dev:release-engineer", project_role="deployer"
    )
    assert payload.project_role == "deployer"


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


@pytest.mark.parametrize("version", [True, 0, -1, 1.5, "1"])
def test_migration_run_cancel_requires_a_strict_positive_version(
    version: object,
) -> None:
    """CAS versions cannot be coerced from booleans, strings, or decimals."""

    with pytest.raises(ValidationError):
        MigrationRunCancelIn(expected_state_version=version)
