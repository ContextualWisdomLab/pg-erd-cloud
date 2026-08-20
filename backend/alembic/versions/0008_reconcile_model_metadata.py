"""reconcile ORM metadata with the existing schema contract

Revision ID: 0008_reconcile_model_metadata
Revises: 0007_api_key
Create Date: 2026-08-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_reconcile_model_metadata"
down_revision = "0007_api_key"
branch_labels = None
depends_on = None


_JSON_COLUMNS = (
    ("schema_snapshot_data", "snapshot_json"),
    ("job_queue", "payload_json"),
    ("diagram_view", "layout_json"),
)


def upgrade() -> None:
    for table_name, column_name in _JSON_COLUMNS:
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.JSON(),
            type_=postgresql.JSONB(),
            existing_nullable=False,
            postgresql_using=f"{column_name}::jsonb",
        )


def downgrade() -> None:
    for table_name, column_name in reversed(_JSON_COLUMNS):
        op.alter_column(
            table_name,
            column_name,
            existing_type=postgresql.JSONB(),
            type_=sa.JSON(),
            existing_nullable=False,
            postgresql_using=f"{column_name}::json",
        )
