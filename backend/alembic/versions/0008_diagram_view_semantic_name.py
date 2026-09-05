"""Rename the saved diagram-view name column semantically.

Revision ID: 0008_diagram_view_semantic_name
Revises: 0007_api_key
Create Date: 2026-09-01

The PostgreSQL column rename is metadata-only, but it requires an
ACCESS EXCLUSIVE table lock. A local lock timeout prevents a deployment from
waiting indefinitely behind an active transaction; operators can retry after
quiescing diagram-view writes. No row rewrite or backfill is required.
"""

from __future__ import annotations

from alembic import op

revision = "0008_diagram_view_semantic_name"
down_revision = "0007_api_key"
branch_labels = None
depends_on = None


def _bound_schema_lock_wait() -> None:
    """Fail closed instead of blocking indefinitely on the metadata rename lock."""
    op.execute("SET LOCAL lock_timeout = '5s'")


def upgrade() -> None:
    """Rename the organization-owned generic column to ``diagram_name``."""
    _bound_schema_lock_wait()
    op.alter_column("diagram_view", "name", new_column_name="diagram_name")


def downgrade() -> None:
    """Restore the historical column name for an explicit rollback."""
    _bound_schema_lock_wait()
    op.alter_column("diagram_view", "diagram_name", new_column_name="name")
