from __future__ import annotations

import json

import httpx
import pytest

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
