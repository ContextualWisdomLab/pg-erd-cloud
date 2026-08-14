from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas import (
    ApplySqlIn,
    ConnectionCreateIn,
    MigrationApplyRunCreateIn,
    MigrationRunCancelIn,
    MigrationRunCreateIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
)


_DISALLOWED_MULTILINE_TEXT_CODE_POINTS = (
    *range(0x00, 0x09),
    0x0B,
    0x0C,
    *range(0x0E, 0x20),
    0x7F,
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


@pytest.mark.parametrize("code_point", _DISALLOWED_MULTILINE_TEXT_CODE_POINTS)
@pytest.mark.parametrize("position", ["beginning", "middle", "end"])
def test_apply_sql_rejects_non_text_controls_at_every_position(
    code_point: int, position: str
) -> None:
    """Reject every disallowed C0 and DEL transport control position."""

    ddl = "CREATE TABLE \"고객\" (note text DEFAULT 'safe');\n"
    control = chr(code_point)
    hostile = {
        "beginning": control + ddl,
        "middle": ddl[:12] + control + ddl[12:],
        "end": ddl + control,
    }[position]

    with pytest.raises(ValidationError) as exc_info:
        ApplySqlIn(sql=hostile)

    assert exc_info.value.errors()[0]["type"] == "string_pattern_mismatch"


@pytest.mark.parametrize("allowed", ["\t", "\n", "\r", " ", "\u0080", "한"])
def test_apply_sql_preserves_multiline_text_boundaries(allowed: str) -> None:
    """Preserve text whitespace and Unicode at the transport boundary."""

    sql = f"CREATE TABLE \"고객\" ({allowed}note text);\r\n-- 설명"
    assert ApplySqlIn(sql=sql).sql == sql


def test_apply_sql_preserves_existing_length_limit() -> None:
    """Keep the accepted 256-KiB character boundary exact."""

    assert len(ApplySqlIn(sql="x" * 262_144).sql) == 262_144
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="x" * 262_145)


@pytest.mark.parametrize("version", [True, 0, -1, 1.5, "1"])
def test_migration_run_cancel_requires_a_strict_positive_version(
    version: object,
) -> None:
    """CAS versions cannot be coerced from booleans, strings, or decimals."""

    with pytest.raises(ValidationError):
        MigrationRunCancelIn(expected_state_version=version)


@pytest.mark.parametrize("digest", ["", "a" * 63, "A" * 64, "g" * 64])
def test_migration_run_create_rejects_invalid_plan_digest(digest: str) -> None:
    """Public run creation accepts only a lowercase SHA-256 plan identity."""

    with pytest.raises(ValidationError):
        MigrationRunCreateIn(plan_digest=digest)


def test_apply_run_create_requires_exact_review_confirmation_shape() -> None:
    """Apply intent input is typed and cannot omit explicit destructive intent."""

    passed_uuid = uuid.uuid4()
    value = MigrationApplyRunCreateIn(
        plan_digest="a" * 64,
        passed_dry_run_uuid=passed_uuid,
        target_connection_name='Production "Primary"',
        destructive_acknowledged=False,
    )
    assert value.passed_dry_run_uuid == passed_uuid
    with pytest.raises(ValidationError):
        MigrationApplyRunCreateIn(
            plan_digest="a" * 64,
            passed_dry_run_uuid=passed_uuid,
            target_connection_name="",
            destructive_acknowledged=False,
        )
    with pytest.raises(ValidationError, match="destructive_acknowledge"):
        MigrationApplyRunCreateIn(
            plan_digest="a" * 64,
            passed_dry_run_uuid=passed_uuid,
            target_connection_name="Production Primary",
            destructive_acknowledged=False,
            destructive_acknowledge=True,
        )
