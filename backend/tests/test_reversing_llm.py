from __future__ import annotations

import datetime as dt
import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.api import share, snapshots
from app.auth import CurrentUser
from app.models import SchemaSnapshot, SchemaSnapshotData, ShareLink
from app.settings import settings
from app.spec.llm import (
    LlmConfigurationError,
    LlmProviderError,
    generate_reversing_llm_draft,
)


def _snapshot() -> dict:
    return {
        "source_dialect": "postgresql",
        "relations": [
            {
                "schema_name": "public",
                "relation_name": "users",
                "relation_oid": 1,
                "relation_kind": "r",
            }
        ],
        "columns": [
            {
                "relation_oid": 1,
                "column_name": "email",
                "data_type": "text",
                "is_not_null": True,
                "example_value": "user@example.com",
            }
        ],
    }


@pytest.mark.asyncio
async def test_generate_reversing_llm_draft_posts_chat_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_api_base_url", "https://llm.example/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        body = json.loads(request.content)
        seen["model"] = body["model"]
        seen["messages"] = body["messages"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "# DB Reversing Specification\n\nDraft"}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        draft = await generate_reversing_llm_draft(_snapshot(), client=client)

    assert draft == "# DB Reversing Specification\n\nDraft"
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["authorization"] == "Bearer test-key"
    assert seen["model"] == "test-model"
    messages = seen["messages"]
    assert isinstance(messages, list)
    assert messages[0]["role"] == "system"
    assert "Do not invent facts" in messages[1]["content"]
    assert "user@example.com" in messages[1]["content"]


@pytest.mark.asyncio
async def test_generate_reversing_llm_draft_requires_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_api_base_url", None)
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")

    with pytest.raises(LlmConfigurationError, match="LLM_API_BASE_URL"):
        await generate_reversing_llm_draft(_snapshot())


@pytest.mark.asyncio
async def test_generate_reversing_llm_draft_rejects_bad_provider_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_api_base_url", "https://llm.example/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"choices": []})
    )

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(LlmProviderError, match="choices"):
            await generate_reversing_llm_draft(_snapshot(), client=client)


@pytest.mark.asyncio
async def test_generate_reversing_llm_draft_rejects_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_api_base_url", "https://llm.example/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=b"not json")
    )

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(LlmProviderError, match="invalid JSON"):
            await generate_reversing_llm_draft(_snapshot(), client=client)


class _SnapshotSession:
    async def get(self, model: object, _: uuid.UUID) -> object:
        assert model is SchemaSnapshotData
        return SimpleNamespace(snapshot_json=_snapshot())


class _ShareSession:
    def __init__(self) -> None:
        self.project_space_uuid = uuid.uuid4()

    async def get(self, model: object, _: uuid.UUID) -> object:
        if model is ShareLink:
            return SimpleNamespace(
                project_space_uuid=self.project_space_uuid,
                expires_at=None,
            )
        if model is SchemaSnapshot:
            return SimpleNamespace(project_space_uuid=self.project_space_uuid)
        assert model is SchemaSnapshotData
        return SimpleNamespace(snapshot_json=_snapshot())


class _ShareLinkScalars:
    def __init__(self, data: list[object]) -> None:
        self.data = data

    def all(self) -> list[object]:
        return self.data


class _ShareLinkResult:
    def __init__(self, data: list[object]) -> None:
        self.data = data

    def scalar_one_or_none(self) -> object:
        return self.data[0] if self.data else None

    def scalars(self) -> _ShareLinkScalars:
        return _ShareLinkScalars(self.data)


class _ShareLinkManagementSession:
    def __init__(self, role: str | None = "owner", links: list[ShareLink] | None = None):
        self.role = role
        self.links = links or []
        self.added: list[ShareLink] = []
        self.deleted: list[ShareLink] = []
        self.execute_count = 0
        self.committed = False

    async def execute(self, _: object) -> _ShareLinkResult:
        self.execute_count += 1
        if self.execute_count == 1:
            return _ShareLinkResult([self.role] if self.role else [])
        return _ShareLinkResult(self.links)

    async def get(self, model: object, _: uuid.UUID) -> object:
        assert model is ShareLink
        return self.links[0] if self.links else None

    def add(self, link: ShareLink) -> None:
        self.added.append(link)

    async def delete(self, link: ShareLink) -> None:
        self.deleted.append(link)

    async def commit(self) -> None:
        self.committed = True


async def _authorized_snapshot(*_: object) -> object:
    return SimpleNamespace()


async def _raise_config_error(_: object) -> str:
    raise LlmConfigurationError("LLM_API_BASE_URL is required for live LLM drafts")


def _current_user() -> CurrentUser:
    return CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject="subject",
        display_name=None,
    )


@pytest.mark.asyncio
async def test_create_share_link_uses_default_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "share_link_default_ttl_hours", 24)
    session = _ShareLinkManagementSession()
    before = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)

    out = await share.create_share_link(
        uuid.uuid4(),
        body=None,
        user=_current_user(),
        session=session,
    )

    after = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)
    assert len(session.added) == 1
    assert out.share_link_uuid == session.added[0].share_link_uuid
    assert out.url_path == f"/api/share/{out.share_link_uuid}"
    assert out.expires_at is not None
    assert before <= out.expires_at <= after
    assert session.committed


@pytest.mark.asyncio
async def test_create_share_link_can_explicitly_disable_expiration() -> None:
    session = _ShareLinkManagementSession()

    out = await share.create_share_link(
        uuid.uuid4(),
        body=share.ShareLinkCreateIn(expires_in_hours=0),
        user=_current_user(),
        session=session,
    )

    assert out.expires_at is None


@pytest.mark.asyncio
async def test_list_share_links_requires_owner() -> None:
    session = _ShareLinkManagementSession(role="viewer")

    with pytest.raises(HTTPException) as exc_info:
        await share.list_share_links(
            uuid.uuid4(),
            user=_current_user(),
            session=session,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "owner role required"


@pytest.mark.asyncio
async def test_delete_share_link_revokes_existing_link() -> None:
    project_uuid = uuid.uuid4()
    link = ShareLink(
        share_link_uuid=uuid.uuid4(),
        project_space_uuid=project_uuid,
        created_by_user_uuid=uuid.uuid4(),
        permission_kind="viewer",
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7),
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    session = _ShareLinkManagementSession(links=[link])

    response = await share.delete_share_link(
        project_uuid,
        link.share_link_uuid,
        user=_current_user(),
        session=session,
    )

    assert response.status_code == 204
    assert session.deleted == [link]
    assert session.committed


def _assert_sanitized_config_error(
    exc_info: pytest.ExceptionInfo[HTTPException],
) -> None:
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "LLM configuration error"
    assert "LLM_API_BASE_URL" not in exc_info.value.detail


def _assert_share_link_llm_draft_disabled(
    exc_info: pytest.ExceptionInfo[HTTPException],
) -> None:
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "share link LLM draft is disabled"


@pytest.mark.asyncio
async def test_snapshot_reversing_draft_hides_llm_configuration_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(snapshots, "_get_authorized_snapshot", _authorized_snapshot)
    monkeypatch.setattr(snapshots, "generate_reversing_llm_draft", _raise_config_error)

    with pytest.raises(HTTPException) as exc_info:
        await snapshots.export_snapshot_reversing_spec(
            uuid.uuid4(),
            mode="llm-draft",
            user=_current_user(),
            session=_SnapshotSession(),
        )

    _assert_sanitized_config_error(exc_info)


@pytest.mark.asyncio
async def test_snapshot_index_design_draft_hides_llm_configuration_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(snapshots, "_get_authorized_snapshot", _authorized_snapshot)
    monkeypatch.setattr(
        snapshots,
        "generate_index_design_llm_draft",
        _raise_config_error,
    )

    with pytest.raises(HTTPException) as exc_info:
        await snapshots.export_snapshot_index_design(
            uuid.uuid4(),
            mode="llm-draft",
            user=_current_user(),
            session=_SnapshotSession(),
        )

    _assert_sanitized_config_error(exc_info)


@pytest.mark.asyncio
async def test_shared_reversing_draft_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "share_link_llm_draft_enabled", False)

    async def _unexpected_llm_call(_: object) -> str:
        pytest.fail("public share link should not call the LLM provider by default")

    monkeypatch.setattr(share, "generate_reversing_llm_draft", _unexpected_llm_call)

    with pytest.raises(HTTPException) as exc_info:
        await share.export_shared_snapshot_reversing_spec(
            uuid.uuid4(),
            uuid.uuid4(),
            mode="llm-draft",
            session=_ShareSession(),
        )

    _assert_share_link_llm_draft_disabled(exc_info)


@pytest.mark.asyncio
async def test_shared_reversing_draft_hides_llm_configuration_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "share_link_llm_draft_enabled", True)
    monkeypatch.setattr(share, "generate_reversing_llm_draft", _raise_config_error)

    with pytest.raises(HTTPException) as exc_info:
        await share.export_shared_snapshot_reversing_spec(
            uuid.uuid4(),
            uuid.uuid4(),
            mode="llm-draft",
            session=_ShareSession(),
        )

    _assert_sanitized_config_error(exc_info)


@pytest.mark.asyncio
async def test_shared_index_design_draft_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "share_link_llm_draft_enabled", False)

    async def _unexpected_llm_call(_: object) -> str:
        pytest.fail("public share link should not call the LLM provider by default")

    monkeypatch.setattr(share, "generate_index_design_llm_draft", _unexpected_llm_call)

    with pytest.raises(HTTPException) as exc_info:
        await share.export_shared_snapshot_index_design(
            uuid.uuid4(),
            uuid.uuid4(),
            mode="llm-draft",
            session=_ShareSession(),
        )

    _assert_share_link_llm_draft_disabled(exc_info)


@pytest.mark.asyncio
async def test_shared_index_design_draft_hides_llm_configuration_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "share_link_llm_draft_enabled", True)
    monkeypatch.setattr(share, "generate_index_design_llm_draft", _raise_config_error)

    with pytest.raises(HTTPException) as exc_info:
        await share.export_shared_snapshot_index_design(
            uuid.uuid4(),
            uuid.uuid4(),
            mode="llm-draft",
            session=_ShareSession(),
        )

    _assert_sanitized_config_error(exc_info)
