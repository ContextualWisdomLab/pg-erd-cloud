from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.share import router
from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.models import (
    ProjectMember,
    SchemaSnapshot,
    SchemaSnapshotData,
    ShareLink,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class FakeResult:
    def __init__(self, data: list[object] | object | None = None):
        self.data = data

    def scalar_one_or_none(self):
        return self.data

    def scalars(self):
        class _Scalars:
            def all(inner_self):
                if isinstance(self.data, list):
                    return self.data
                return [self.data] if self.data is not None else []
                return self.data
        return _Scalars()


class FakeSession:
    def __init__(self, execute_result=None, get_results=None):
        self.execute_result = execute_result
        self.get_results = get_results or {}
        self.added = []
        self.committed = False

    async def execute(self, query):
        if isinstance(self.execute_result, list):
            return FakeResult(self.execute_result.pop(0) if self.execute_result else None)
        return FakeResult(self.execute_result)

    async def get(self, model, ident):
        return self.get_results.get((model, ident))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


def get_fake_user():
    return CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject="test-subject",
        display_name="Test User",
    )

app.dependency_overrides[get_current_user] = get_fake_user


@pytest.mark.asyncio
async def test_create_share_link_success():
    project_uuid = uuid.uuid4()

    session = FakeSession(execute_result="owner")
    app.dependency_overrides[get_session] = lambda: session

    response = client.post(f"/api/projects/{project_uuid}/share-links")
    assert response.status_code == 200
    data = response.json()
    assert "share_link_uuid" in data
    assert data["permission_kind"] == "viewer"
    assert "url_path" in data
    assert session.committed
    assert len(session.added) == 1
    assert isinstance(session.added[0], ShareLink)


@pytest.mark.asyncio
async def test_create_share_link_forbidden():
    project_uuid = uuid.uuid4()

    session = FakeSession(execute_result="viewer")
    app.dependency_overrides[get_session] = lambda: session

    response = client.post(f"/api/projects/{project_uuid}/share-links")
    assert response.status_code == 403
    assert response.json()["detail"] == "owner role required"


@pytest.mark.asyncio
async def test_get_share_link_info_success():
    share_link_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )

    snapshot_uuid = uuid.uuid4()
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
        created_at=dt.datetime.now(dt.timezone.utc),
    )

    session = FakeSession(
        execute_result=[snap],
        get_results={(ShareLink, share_link_uuid): link}
    )
    app.dependency_overrides[get_read_session] = lambda: session

    response = client.get(f"/api/share/{share_link_uuid}")
    assert response.status_code == 200
    data = response.json()
    assert data["project_space_uuid"] == str(project_space_uuid)
    assert len(data["snapshots"]) == 1
    assert data["snapshots"][0]["schema_snapshot_uuid"] == str(snapshot_uuid)


@pytest.mark.asyncio
async def test_get_share_link_info_not_found():
    share_link_uuid = uuid.uuid4()

    session = FakeSession(get_results={})
    app.dependency_overrides[get_read_session] = lambda: session

    response = client.get(f"/api/share/{share_link_uuid}")
    assert response.status_code == 404
    assert response.json()["detail"] == "share link not found"


@pytest.mark.asyncio
async def test_get_share_link_info_expired():
    share_link_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )

    session = FakeSession(get_results={(ShareLink, share_link_uuid): link})
    app.dependency_overrides[get_read_session] = lambda: session

    response = client.get(f"/api/share/{share_link_uuid}")
    assert response.status_code == 410
    assert response.json()["detail"] == "share link expired"

@pytest.mark.asyncio
async def test_get_shared_snapshot_success():
    share_link_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )

    snapshot_uuid = uuid.uuid4()
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
        error_message=None,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    data = SchemaSnapshotData(
        schema_snapshot_uuid=snapshot_uuid,
        snapshot_json={"tables": []},
    )

    session = FakeSession(
        get_results={
            (ShareLink, share_link_uuid): link,
            (SchemaSnapshot, snapshot_uuid): snap,
            (SchemaSnapshotData, snapshot_uuid): data,
        }
    )
    app.dependency_overrides[get_read_session] = lambda: session

    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["schema_snapshot_uuid"] == str(snapshot_uuid)
    assert res_data["snapshot_json"] == {"tables": []}


@pytest.mark.asyncio
async def test_export_shared_snapshot_sql_success():
    share_link_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )

    snapshot_uuid = uuid.uuid4()
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    data = SchemaSnapshotData(
        schema_snapshot_uuid=snapshot_uuid,
        snapshot_json={"tables": []},
    )

    session = FakeSession(
        get_results={
            (ShareLink, share_link_uuid): link,
            (SchemaSnapshot, snapshot_uuid): snap,
            (SchemaSnapshotData, snapshot_uuid): data,
        }
    )
    app.dependency_overrides[get_read_session] = lambda: session

    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/export.sql")
    assert response.status_code == 200
    assert "-- Generated by pg-erd-cloud" in response.text


@pytest.mark.asyncio
async def test_export_shared_snapshot_reversing_spec_success():
    share_link_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )

    snapshot_uuid = uuid.uuid4()
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    data = SchemaSnapshotData(
        schema_snapshot_uuid=snapshot_uuid,
        snapshot_json={"tables": []},
    )

    session = FakeSession(
        get_results={
            (ShareLink, share_link_uuid): link,
            (SchemaSnapshot, snapshot_uuid): snap,
            (SchemaSnapshotData, snapshot_uuid): data,
        }
    )
    app.dependency_overrides[get_read_session] = lambda: session

    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/reversing-spec.md")
    assert response.status_code == 200
    assert "# DB Reversing Specification" in response.text


@pytest.mark.asyncio
async def test_export_shared_snapshot_index_design_success():
    share_link_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )

    snapshot_uuid = uuid.uuid4()
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    data = SchemaSnapshotData(
        schema_snapshot_uuid=snapshot_uuid,
        snapshot_json={"tables": []},
    )

    session = FakeSession(
        get_results={
            (ShareLink, share_link_uuid): link,
            (SchemaSnapshot, snapshot_uuid): snap,
            (SchemaSnapshotData, snapshot_uuid): data,
        }
    )
    app.dependency_overrides[get_read_session] = lambda: session

    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/index-design.md")
    assert response.status_code == 200
    assert "# ERD Index Design" in response.text

@pytest.mark.asyncio
async def test_get_shared_snapshot_not_found():
    share_link_uuid = uuid.uuid4()

    session = FakeSession(get_results={})
    app.dependency_overrides[get_read_session] = lambda: session

    snapshot_uuid = uuid.uuid4()
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}")
    assert response.status_code == 404
    assert response.json()["detail"] == "share link not found"

@pytest.mark.asyncio
async def test_get_shared_snapshot_snapshot_not_found():
    share_link_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )

    session = FakeSession(get_results={(ShareLink, share_link_uuid): link})
    app.dependency_overrides[get_read_session] = lambda: session

    snapshot_uuid = uuid.uuid4()
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}")
    assert response.status_code == 404
    assert response.json()["detail"] == "snapshot not found"

@pytest.mark.asyncio
async def test_get_shared_snapshot_expired():
    share_link_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )

    session = FakeSession(get_results={(ShareLink, share_link_uuid): link})
    app.dependency_overrides[get_read_session] = lambda: session

    snapshot_uuid = uuid.uuid4()
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}")
    assert response.status_code == 410
    assert response.json()["detail"] == "share link expired"


@pytest.mark.asyncio
async def test_export_shared_snapshot_sql_not_found_cases():
    share_link_uuid = uuid.uuid4()
    snapshot_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()

    # 1. link not found
    session = FakeSession(get_results={})
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/export.sql")
    assert response.status_code == 404

    # 2. link expired
    link_expired = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )
    session = FakeSession(get_results={(ShareLink, share_link_uuid): link_expired})
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/export.sql")
    assert response.status_code == 410

    # 3. snapshot not found
    link_valid = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )
    session = FakeSession(get_results={(ShareLink, share_link_uuid): link_valid})
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/export.sql")
    assert response.status_code == 404

    # 4. snapshot data not found
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
    )
    session = FakeSession(get_results={
        (ShareLink, share_link_uuid): link_valid,
        (SchemaSnapshot, snapshot_uuid): snap
    })
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/export.sql")
    assert response.status_code == 200
    assert response.text == "-- snapshot data not found\n"


@pytest.mark.asyncio
async def test_export_shared_snapshot_reversing_spec_not_found_cases():
    share_link_uuid = uuid.uuid4()
    snapshot_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()

    # 1. link not found
    session = FakeSession(get_results={})
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/reversing-spec.md")
    assert response.status_code == 404

    # 2. link expired
    link_expired = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )
    session = FakeSession(get_results={(ShareLink, share_link_uuid): link_expired})
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/reversing-spec.md")
    assert response.status_code == 410

    # 3. snapshot not found
    link_valid = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )
    session = FakeSession(get_results={(ShareLink, share_link_uuid): link_valid})
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/reversing-spec.md")
    assert response.status_code == 404

    # 4. snapshot data not found
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
    )
    session = FakeSession(get_results={
        (ShareLink, share_link_uuid): link_valid,
        (SchemaSnapshot, snapshot_uuid): snap
    })
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/reversing-spec.md")
    assert response.status_code == 200
    assert response.text == "# DB Reversing Specification\n\nSnapshot data not found.\n"


@pytest.mark.asyncio
async def test_export_shared_snapshot_index_design_not_found_cases():
    share_link_uuid = uuid.uuid4()
    snapshot_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()

    # 1. link not found
    session = FakeSession(get_results={})
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/index-design.md")
    assert response.status_code == 404

    # 2. link expired
    link_expired = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )
    session = FakeSession(get_results={(ShareLink, share_link_uuid): link_expired})
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/index-design.md")
    assert response.status_code == 410

    # 3. snapshot not found
    link_valid = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )
    session = FakeSession(get_results={(ShareLink, share_link_uuid): link_valid})
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/index-design.md")
    assert response.status_code == 404

    # 4. snapshot data not found
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
    )
    session = FakeSession(get_results={
        (ShareLink, share_link_uuid): link_valid,
        (SchemaSnapshot, snapshot_uuid): snap
    })
    app.dependency_overrides[get_read_session] = lambda: session
    response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/index-design.md")
    assert response.status_code == 200
    assert response.text == "# ERD Index Design\n\nSnapshot data not found.\n"


from unittest.mock import patch
from app.spec.llm import LlmConfigurationError, LlmProviderError

@pytest.mark.asyncio
async def test_export_shared_snapshot_reversing_spec_llm_draft():
    share_link_uuid = uuid.uuid4()
    snapshot_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()

    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
    )
    data = SchemaSnapshotData(
        schema_snapshot_uuid=snapshot_uuid,
        snapshot_json={"tables": []},
    )

    session = FakeSession(get_results={
        (ShareLink, share_link_uuid): link,
        (SchemaSnapshot, snapshot_uuid): snap,
        (SchemaSnapshotData, snapshot_uuid): data,
    })
    app.dependency_overrides[get_read_session] = lambda: session

    # 1. Success
    with patch("app.api.share.generate_reversing_llm_draft") as mock_gen:
        mock_gen.return_value = "draft content"
        response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/reversing-spec.md?mode=llm-draft")
        assert response.status_code == 200
        assert response.text == "draft content"

    # 2. LlmConfigurationError
    with patch("app.api.share.generate_reversing_llm_draft") as mock_gen:
        mock_gen.side_effect = LlmConfigurationError("config err")
        response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/reversing-spec.md?mode=llm-draft")
        assert response.status_code == 503
        assert response.json()["detail"] == "config err"

    # 3. LlmProviderError
    with patch("app.api.share.generate_reversing_llm_draft") as mock_gen:
        mock_gen.side_effect = LlmProviderError("provider err")
        response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/reversing-spec.md?mode=llm-draft")
        assert response.status_code == 502


@pytest.mark.asyncio
async def test_export_shared_snapshot_index_design_llm_draft():
    share_link_uuid = uuid.uuid4()
    snapshot_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()

    link = ShareLink(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
        expires_at=None,
    )
    snap = SchemaSnapshot(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="completed",
        schema_filter=None,
    )
    data = SchemaSnapshotData(
        schema_snapshot_uuid=snapshot_uuid,
        snapshot_json={"tables": []},
    )

    session = FakeSession(get_results={
        (ShareLink, share_link_uuid): link,
        (SchemaSnapshot, snapshot_uuid): snap,
        (SchemaSnapshotData, snapshot_uuid): data,
    })
    app.dependency_overrides[get_read_session] = lambda: session

    # 1. Success
    with patch("app.api.share.generate_index_design_llm_draft") as mock_gen:
        mock_gen.return_value = "index draft"
        response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/index-design.md?mode=llm-draft")
        assert response.status_code == 200
        assert response.text == "index draft"

    # 2. LlmConfigurationError
    with patch("app.api.share.generate_index_design_llm_draft") as mock_gen:
        mock_gen.side_effect = LlmConfigurationError("config err")
        response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/index-design.md?mode=llm-draft")
        assert response.status_code == 503
        assert response.json()["detail"] == "config err"

    # 3. LlmProviderError
    with patch("app.api.share.generate_index_design_llm_draft") as mock_gen:
        mock_gen.side_effect = LlmProviderError("provider err")
        response = client.get(f"/api/share/{share_link_uuid}/snapshots/{snapshot_uuid}/index-design.md?mode=llm-draft")
        assert response.status_code == 502
