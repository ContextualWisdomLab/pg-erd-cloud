"""revoked_token

Revision ID: 0003
Revises: 0002_auth_share
Create Date: 2026-06-22 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002_auth_share"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revoked_token",
        sa.Column("jwt_id", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jwt_id"),
    )


def downgrade() -> None:
    op.drop_table("revoked_token")
