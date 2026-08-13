"""persist terminal worker acknowledgement of cancellation intent

Revision ID: 0013_migration_run_cancellation
Revises: 0012_apply_intent_confirmation
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op

revision = "0013_migration_run_cancellation"
down_revision = "0012_apply_intent_confirmation"
branch_labels = None
depends_on = None

_RUN_STATES = (
    "'queued', 'sandbox_running', 'live_preflight_running', 'passed', "
    "'drifted', 'failed', 'applying', 'reconciling', 'verifying', "
    "'verified', 'drifted_no_apply', 'not_applied', 'verification_failed', "
    "'failed_rolled_back', 'applied_with_drift', 'outcome_unknown'"
)
_RUN_STATES_WITH_CANCELLED = f"{_RUN_STATES}, 'cancelled'"
_DRY_RUN_STATES = (
    "'queued', 'sandbox_running', 'live_preflight_running', 'passed', "
    "'drifted', 'failed'"
)
_APPLY_RUN_STATES = (
    "'queued', 'applying', 'reconciling', 'verifying', 'verified', "
    "'drifted_no_apply', 'not_applied', 'verification_failed', "
    "'failed_rolled_back', 'applied_with_drift', 'outcome_unknown'"
)


def _replace_state_constraints(*, include_cancelled: bool) -> None:
    """Replace run/event checks while preserving every predecessor state."""

    for table_name, constraint_name in (
        ("migration_run_event", "ck_migration_run_event__state_after"),
        ("migration_run_event", "ck_migration_run_event__state_before"),
        ("migration_run", "ck_migration_run__kind_state"),
        ("migration_run", "ck_migration_run__state"),
    ):
        op.drop_constraint(constraint_name, table_name, type_="check")

    states = _RUN_STATES_WITH_CANCELLED if include_cancelled else _RUN_STATES
    dry_run_states = (
        f"{_DRY_RUN_STATES}, 'cancelled'"
        if include_cancelled
        else _DRY_RUN_STATES
    )
    apply_run_states = (
        f"{_APPLY_RUN_STATES}, 'cancelled'"
        if include_cancelled
        else _APPLY_RUN_STATES
    )
    op.create_check_constraint(
        "ck_migration_run__state",
        "migration_run",
        f"state IN ({states})",
    )
    op.create_check_constraint(
        "ck_migration_run__kind_state",
        "migration_run",
        "(run_kind = 'dry_run' AND "
        f"state IN ({dry_run_states})) OR "
        "(run_kind = 'apply' AND "
        f"state IN ({apply_run_states}))",
    )
    op.create_check_constraint(
        "ck_migration_run_event__state_before",
        "migration_run_event",
        f"state_before IS NULL OR state_before IN ({states})",
    )
    op.create_check_constraint(
        "ck_migration_run_event__state_after",
        "migration_run_event",
        f"state_after IN ({states})",
    )


def upgrade() -> None:
    """Admit one terminal state that acknowledges persisted cancellation."""

    _replace_state_constraints(include_cancelled=True)


def downgrade() -> None:
    """Restore predecessor checks, failing if cancelled evidence still exists."""

    _replace_state_constraints(include_cancelled=False)
