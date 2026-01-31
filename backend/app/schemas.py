from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ProjectCreateIn(BaseModel):
    project_name: str = Field(min_length=1)


class ProjectOut(BaseModel):
    project_space_uuid: uuid.UUID
    project_name: str


class ConnectionCreateIn(BaseModel):
    conn_name: str = Field(min_length=1)
    dsn: str = Field(
        min_length=1, description="PostgreSQL connection string. Not logged."
    )


class ConnectionOut(BaseModel):
    db_connection_uuid: uuid.UUID
    conn_name: str


class SnapshotCreateIn(BaseModel):
    db_connection_uuid: uuid.UUID
    schema_filter: str | None = Field(
        default=None, description="If set, only introspect this schema"
    )


class SnapshotOut(BaseModel):
    schema_snapshot_uuid: uuid.UUID
    status: str
    schema_filter: str | None


class SnapshotDetailOut(BaseModel):
    schema_snapshot_uuid: uuid.UUID
    status: str
    schema_filter: str | None
    error_message: str | None
    snapshot_json: dict | None
