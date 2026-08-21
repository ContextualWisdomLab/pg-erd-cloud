from __future__ import annotations

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


def _assert_sanitized_config_error(
    exc_info: pytest.ExceptionInfo[HTTPException],
) -> None:
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "LLM configuration error"
    assert "LLM_API_BASE_URL" not in exc_info.value.detail


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
async def test_shared_reversing_draft_hides_llm_configuration_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
async def test_shared_index_design_draft_hides_llm_configuration_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(share, "generate_index_design_llm_draft", _raise_config_error)

    with pytest.raises(HTTPException) as exc_info:
        await share.export_shared_snapshot_index_design(
            uuid.uuid4(),
            uuid.uuid4(),
            mode="llm-draft",
            session=_ShareSession(),
        )

    _assert_sanitized_config_error(exc_info)
