from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, LargeBinary, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for ORM models."""

    pass


def utcnow() -> dt.datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return dt.datetime.now(dt.timezone.utc)


class UserAccount(Base):
    """User record keyed by a UUID and identified by OIDC subject."""

    __tablename__ = "user_account"

    user_account_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    oidc_subject: Mapped[str] = mapped_column(Text(), unique=True)
    display_name: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class ProjectSpace(Base):
    """Project container that groups connections and snapshots."""

    __tablename__ = "project_space"

    project_space_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_name: Mapped[str] = mapped_column(Text())
    created_by_user_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_account.user_account_uuid")
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class ProjectMember(Base):
    """Membership mapping between users and projects with a role."""

    __tablename__ = "project_member"

    project_space_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_space.project_space_uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    user_account_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_account.user_account_uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    project_role: Mapped[str] = mapped_column(Text())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    __table_args__ = (
        Index("ix_project_member__user_account_uuid", "user_account_uuid"),
    )


class DbConnection(Base):
    """Encrypted PostgreSQL DSN belonging to a project."""

    __tablename__ = "db_connection"

    db_connection_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_space_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_space.project_space_uuid", ondelete="CASCADE"),
        index=True,
    )
    conn_name: Mapped[str] = mapped_column(Text())
    dsn_ciphertext: Mapped[bytes] = mapped_column(LargeBinary())
    dsn_nonce: Mapped[bytes] = mapped_column(LargeBinary())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class SchemaSnapshot(Base):
    """Snapshot job record for a database introspection run."""

    __tablename__ = "schema_snapshot"

    schema_snapshot_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_space_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_space.project_space_uuid", ondelete="CASCADE"),
        index=True,
    )
    db_connection_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("db_connection.db_connection_uuid", ondelete="CASCADE"),
    )
    status: Mapped[str] = mapped_column(Text())
    schema_filter: Mapped[str | None] = mapped_column(Text(), nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class SchemaSnapshotData(Base):
    """Captured schema snapshot JSON payload."""

    __tablename__ = "schema_snapshot_data"

    schema_snapshot_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schema_snapshot.schema_snapshot_uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    snapshot_json: Mapped[dict] = mapped_column(JSONB())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class JobQueue(Base):
    """Lightweight DB-backed job queue (MVP)."""

    __tablename__ = "job_queue"

    job_queue_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(Text())
    payload_json: Mapped[dict] = mapped_column(JSONB())
    run_after: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0)
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_job_queue__status_run_after", "status", "run_after"),
    )


class ShareLink(Base):
    """Public share link granting read access to a project's snapshots."""

    __tablename__ = "share_link"

    share_link_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_space_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_space.project_space_uuid", ondelete="CASCADE"),
        index=True,
    )
    created_by_user_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_account.user_account_uuid", ondelete="CASCADE"),
    )
    permission_kind: Mapped[str] = mapped_column(
        Text()
    )  # viewer/editor (MVP: viewer)
    expires_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
