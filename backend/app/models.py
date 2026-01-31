from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, LargeBinary, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class UserAccount(Base):
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
    __tablename__ = "project_member"

    project_space_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_space.project_space_uuid"),
        primary_key=True,
    )
    user_account_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_account.user_account_uuid"),
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
    __tablename__ = "db_connection"

    db_connection_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_space_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_space.project_space_uuid"), index=True
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
    __tablename__ = "schema_snapshot"

    schema_snapshot_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_space_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_space.project_space_uuid"), index=True
    )
    db_connection_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("db_connection.db_connection_uuid")
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
    __tablename__ = "schema_snapshot_data"

    schema_snapshot_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schema_snapshot.schema_snapshot_uuid"),
        primary_key=True,
    )
    snapshot_json: Mapped[dict] = mapped_column(JSONB())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class JobQueue(Base):
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

    __table_args__ = (Index("ix_job_queue__status_run_after", "status", "run_after"),)


class ShareLink(Base):
    __tablename__ = "share_link"

    share_link_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_space_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_space.project_space_uuid"), index=True
    )
    created_by_user_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_account.user_account_uuid")
    )
    permission_kind: Mapped[str] = mapped_column(Text())  # viewer/editor (MVP: viewer)
    expires_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
