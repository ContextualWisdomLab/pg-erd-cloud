"""merge revoked_token and validate_project_space_fk into a single head

Two migrations branched independently from 0002_auth_share:
  - 0003 (revoked_token): creates the revoked_token table
  - 0003_validate_project_space_fk: validates a project_space FK
They are unrelated and safe to apply in any order, so this is a no-op merge
that unifies the graph to a single head (``alembic upgrade head`` was ambiguous
with two heads).

Revision ID: 0004_merge_heads
Revises: 0003, 0003_validate_project_space_fk
Create Date: 2026-07-05 00:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = "0004_merge_heads"
down_revision = ("0003", "0003_validate_project_space_fk")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No schema change; this revision only merges two heads."""


def downgrade() -> None:
    """No schema change; splitting back into two heads requires no work."""
