from __future__ import annotations

import datetime as dt
import json
import logging
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from prometheus_client import REGISTRY

from app.api import share, snapshots
from app.auth import CurrentUser
from app.models import SchemaSnapshot, SchemaSnapshotData, ShareLink
from app.settings import settings
from app.spec.llm import (
    LlmConfigurationError,
    LlmPromptTooLargeError,
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


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        headers={"user-agent": "pytest"},
        client=SimpleNamespace(host="127.0.0.1"),
        state=SimpleNamespace(request_id="test-request-id"),
    )


def _share_audit_events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for record in caplog.records:
        if record.name != "app.share":
            continue
        try:
            payload = json.loads(record.getMessage())
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "share_audit":
            events.append(payload)
    return events


def _llm_usage_events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for record in caplog.records:
        if record.name != "app.llm_usage":
            continue
        try:
            payload = json.loads(record.getMessage())
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "llm_draft_usage":
            events.append(payload)
    return events


def _llm_draft_metric_value(
    *,
    surface: str,
    artifact: str,
    outcome: str,
) -> float:
    value = REGISTRY.get_sample_value(
        "llm_draft_requests_total",
        {"surface": surface, "artifact": artifact, "outcome": outcome},
    )
    return float(value or 0.0)


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
        seen["max_tokens"] = body["max_tokens"]
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
    assert seen["max_tokens"] == settings.llm_max_output_tokens
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
async def test_generate_reversing_llm_draft_rejects_oversized_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_api_base_url", "https://llm.example/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(settings, "llm_max_prompt_chars", 1_000)

    snapshot = _snapshot()
    snapshot["relations"] = [
        {
            "schema_name": "public",
            "relation_name": f"large_table_{i}",
            "relation_oid": i,
            "relation_kind": "r",
        }
        for i in range(300)
    ]

    with pytest.raises(LlmPromptTooLargeError):
        await generate_reversing_llm_draft(snapshot)


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


async def _raise_prompt_too_large(_: object) -> str:
    raise LlmPromptTooLargeError("prompt too large")


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
        request=_request(),
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
        request=_request(),
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
            request=_request(),
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
        request=_request(),
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


def _assert_prompt_too_large_error(
    exc_info: pytest.ExceptionInfo[HTTPException],
) -> None:
    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "LLM prompt too large"


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
async def test_snapshot_reversing_draft_records_usage_metric_and_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    project_uuid = uuid.uuid4()
    snapshot_uuid = uuid.uuid4()
    user = _current_user()

    async def _authorized_snapshot_with_project(*_: object) -> object:
        return SimpleNamespace(project_space_uuid=project_uuid)

    async def _draft(_: object) -> str:
        return "# DB Reversing Specification\n\nDraft"

    monkeypatch.setattr(
        snapshots, "_get_authorized_snapshot", _authorized_snapshot_with_project
    )
    monkeypatch.setattr(snapshots, "generate_reversing_llm_draft", _draft)
    before = _llm_draft_metric_value(
        surface="authenticated",
        artifact="reversing_spec",
        outcome="success",
    )

    with caplog.at_level(logging.INFO, logger="app.llm_usage"):
        result = await snapshots.export_snapshot_reversing_spec(
            snapshot_uuid,
            mode="llm-draft",
            user=user,
            session=_SnapshotSession(),
        )

    assert result == "# DB Reversing Specification\n\nDraft"
    assert (
        _llm_draft_metric_value(
            surface="authenticated",
            artifact="reversing_spec",
            outcome="success",
        )
        == before + 1
    )
    events = _llm_usage_events(caplog)
    assert events
    assert events[-1]["surface"] == "authenticated"
    assert events[-1]["artifact"] == "reversing_spec"
    assert events[-1]["outcome"] == "success"
    assert events[-1]["user_account_uuid"] == str(user.user_account_uuid)
    assert events[-1]["project_space_uuid"] == str(project_uuid)
    assert events[-1]["schema_snapshot_uuid"] == str(snapshot_uuid)
    assert isinstance(events[-1]["input_chars"], int)
    assert events[-1]["input_chars"] > 0
    assert events[-1]["output_chars"] == len(result)


@pytest.mark.asyncio
async def test_snapshot_reversing_draft_rejects_oversized_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(snapshots, "_get_authorized_snapshot", _authorized_snapshot)
    monkeypatch.setattr(
        snapshots, "generate_reversing_llm_draft", _raise_prompt_too_large
    )

    with pytest.raises(HTTPException) as exc_info:
        await snapshots.export_snapshot_reversing_spec(
            uuid.uuid4(),
            mode="llm-draft",
            user=_current_user(),
            session=_SnapshotSession(),
        )

    _assert_prompt_too_large_error(exc_info)


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
            request=_request(),
            session=_ShareSession(),
        )

    _assert_share_link_llm_draft_disabled(exc_info)


@pytest.mark.asyncio
async def test_shared_reversing_draft_disabled_event_is_audited(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "share_link_llm_draft_enabled", False)

    with caplog.at_level(logging.INFO, logger="app.share"):
        with pytest.raises(HTTPException) as exc_info:
            await share.export_shared_snapshot_reversing_spec(
                uuid.uuid4(),
                uuid.uuid4(),
                mode="llm-draft",
                request=_request(),
                session=_ShareSession(),
            )
    _assert_share_link_llm_draft_disabled(exc_info)

    events = _share_audit_events(caplog)
    assert events
    assert events[-1]["request_id"] == "test-request-id"
    assert events[-1]["action"] == "share_snapshot.reversing_spec"
    assert events[-1]["outcome"] == "denied"
    assert events[-1]["mode"] == "llm-draft"
    assert events[-1]["error_detail"] == "share link LLM draft is disabled"


@pytest.mark.asyncio
async def test_shared_reversing_draft_disabled_records_usage_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "share_link_llm_draft_enabled", False)
    before = _llm_draft_metric_value(
        surface="share_link",
        artifact="reversing_spec",
        outcome="disabled",
    )

    with pytest.raises(HTTPException):
        await share.export_shared_snapshot_reversing_spec(
            uuid.uuid4(),
            uuid.uuid4(),
            mode="llm-draft",
            request=_request(),
            session=_ShareSession(),
        )

    assert (
        _llm_draft_metric_value(
            surface="share_link",
            artifact="reversing_spec",
            outcome="disabled",
        )
        == before + 1
    )


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
            request=_request(),
            session=_ShareSession(),
        )

    _assert_sanitized_config_error(exc_info)


@pytest.mark.asyncio
async def test_shared_reversing_draft_configuration_error_event_is_audited(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "share_link_llm_draft_enabled", True)
    monkeypatch.setattr(share, "generate_reversing_llm_draft", _raise_config_error)

    with caplog.at_level(logging.INFO, logger="app.share"):
        with pytest.raises(HTTPException) as exc_info:
            await share.export_shared_snapshot_reversing_spec(
                uuid.uuid4(),
                uuid.uuid4(),
                mode="llm-draft",
                request=_request(),
                session=_ShareSession(),
            )

    _assert_sanitized_config_error(exc_info)
    events = _share_audit_events(caplog)
    assert events
    assert events[-1]["request_id"] == "test-request-id"
    assert events[-1]["action"] == "share_snapshot.reversing_spec"
    assert events[-1]["outcome"] == "failed"
    assert events[-1]["mode"] == "llm-draft"
    assert events[-1]["error_detail"] == "LLM configuration error"


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
            request=_request(),
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
            request=_request(),
            session=_ShareSession(),
        )

    _assert_sanitized_config_error(exc_info)


@pytest.mark.asyncio
async def test_shared_index_design_draft_disabled_event_is_audited(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "share_link_llm_draft_enabled", False)

    with caplog.at_level(logging.INFO, logger="app.share"):
        with pytest.raises(HTTPException) as exc_info:
            await share.export_shared_snapshot_index_design(
                uuid.uuid4(),
                uuid.uuid4(),
                mode="llm-draft",
                request=_request(),
                session=_ShareSession(),
            )

    _assert_share_link_llm_draft_disabled(exc_info)
    events = _share_audit_events(caplog)
    assert events
    assert events[-1]["request_id"] == "test-request-id"
    assert events[-1]["action"] == "share_snapshot.index_design"
    assert events[-1]["outcome"] == "denied"
    assert events[-1]["mode"] == "llm-draft"
    assert events[-1]["error_detail"] == "share link LLM draft is disabled"


@pytest.mark.asyncio
async def test_shared_index_design_draft_configuration_error_event_is_audited(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "share_link_llm_draft_enabled", True)
    monkeypatch.setattr(share, "generate_index_design_llm_draft", _raise_config_error)

    with caplog.at_level(logging.INFO, logger="app.share"):
        with pytest.raises(HTTPException) as exc_info:
            await share.export_shared_snapshot_index_design(
                uuid.uuid4(),
                uuid.uuid4(),
                mode="llm-draft",
                request=_request(),
                session=_ShareSession(),
            )

    _assert_sanitized_config_error(exc_info)
    events = _share_audit_events(caplog)
    assert events
    assert events[-1]["request_id"] == "test-request-id"
    assert events[-1]["action"] == "share_snapshot.index_design"
    assert events[-1]["outcome"] == "failed"
    assert events[-1]["mode"] == "llm-draft"
    assert events[-1]["error_detail"] == "LLM configuration error"


@pytest.mark.asyncio
async def test_share_link_create_audit_event_is_emitted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = _ShareLinkManagementSession()
    project_uuid = uuid.uuid4()

    with caplog.at_level(logging.INFO, logger="app.share"):
        out = await share.create_share_link(
            project_uuid,
            body=None,
            request=_request(),
            user=_current_user(),
            session=session,
        )

    events = _share_audit_events(caplog)
    assert events
    assert events[-1]["action"] == "share_link.create"
    assert events[-1]["outcome"] == "success"
    assert events[-1]["project_space_uuid"] == str(project_uuid)
    assert events[-1]["share_link_uuid"] == str(out.share_link_uuid)


@pytest.mark.asyncio
async def test_share_link_list_denied_audit_event_is_emitted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = _ShareLinkManagementSession(role="viewer")

    with caplog.at_level(logging.INFO, logger="app.share"):
        with pytest.raises(HTTPException):
            await share.list_share_links(
                uuid.uuid4(),
                request=_request(),
                user=_current_user(),
                session=session,
            )

    events = _share_audit_events(caplog)
    assert events
    assert events[-1]["action"] == "share_link.list"
    assert events[-1]["outcome"] == "denied"
    assert events[-1]["error_detail"] == "owner role required"


@pytest.mark.asyncio
async def test_share_snapshot_reversing_spec_audit_event_is_emitted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = _ShareSession()

    with caplog.at_level(logging.INFO, logger="app.share"):
        await share.export_shared_snapshot_reversing_spec(
            uuid.uuid4(),
            uuid.uuid4(),
            mode="markdown",
            request=_request(),
            session=session,
        )

    events = _share_audit_events(caplog)
    assert events
    assert events[-1]["request_id"] == "test-request-id"
    assert events[-1]["action"] == "share_snapshot.reversing_spec"
    assert events[-1]["outcome"] == "success"
    assert events[-1]["mode"] == "markdown"
