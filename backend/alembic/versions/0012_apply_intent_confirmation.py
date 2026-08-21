"""bind apply intents to exact reviewed dry-run confirmation

Revision ID: 0012_apply_intent_confirmation
Revises: 0011_migration_run_attempt
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_apply_intent_confirmation"
down_revision = "0011_migration_run_attempt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add immutable reviewed-input bindings without adding execution authority."""

    op.add_column(
        "migration_run",
        sa.Column("passed_dry_run_uuid", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "migration_run", sa.Column("confirmation_digest", sa.Text(), nullable=True)
    )
    op.add_column(
        "migration_run",
        sa.Column("destructive_confirmation", sa.Boolean(), nullable=True),
    )
    op.create_foreign_key(
        "fk_migration_run__passed_dry_run_uuid",
        "migration_run",
        "migration_run",
        ["passed_dry_run_uuid"],
        ["migration_run_uuid"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_migration_run__confirmation_digest",
        "migration_run",
        "confirmation_digest IS NULL OR confirmation_digest ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "ck_migration_run__apply_confirmation",
        "migration_run",
        "(run_kind = 'dry_run' AND passed_dry_run_uuid IS NULL AND "
        "confirmation_digest IS NULL AND destructive_confirmation IS NULL) OR "
        "(run_kind = 'apply' AND passed_dry_run_uuid IS NOT NULL AND "
        "confirmation_digest IS NOT NULL AND destructive_confirmation IS NOT NULL)",
    )
    op.create_index(
        "ix_migration_run__passed_dry_run_uuid",
        "migration_run",
        ["passed_dry_run_uuid"],
    )


def downgrade() -> None:
    """Remove apply-intent confirmation bindings."""

    op.drop_index("ix_migration_run__passed_dry_run_uuid", table_name="migration_run")
    op.drop_constraint(
        "ck_migration_run__apply_confirmation", "migration_run", type_="check"
    )
    op.drop_constraint(
        "ck_migration_run__confirmation_digest", "migration_run", type_="check"
    )
    op.drop_constraint(
        "fk_migration_run__passed_dry_run_uuid", "migration_run", type_="foreignkey"
    )
    op.drop_column("migration_run", "destructive_confirmation")
    op.drop_column("migration_run", "confirmation_digest")
    op.drop_column("migration_run", "passed_dry_run_uuid")
