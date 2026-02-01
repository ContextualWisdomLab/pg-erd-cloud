"""validate project_space created_by FK

Revision ID: 0003_validate_project_space_fk
Revises: 0002_auth_share
Create Date: 2026-02-01

"""

from __future__ import annotations

from alembic import op

revision = "0003_validate_project_space_fk"
down_revision = "0002_auth_share"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Validate the FK created as NOT VALID in 0002.
    op.execute(
        "ALTER TABLE project_space VALIDATE CONSTRAINT fk_project_space__created_by_user;"
    )


def downgrade() -> None:
    # No-op: validation does not require rollback.
    pass
