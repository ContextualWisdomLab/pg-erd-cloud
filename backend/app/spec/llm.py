from __future__ import annotations

import httpx

from app.settings import settings
from app.spec.index_design import generate_index_design_llm_prompt
from app.spec.reversing import generate_reversing_llm_prompt


class LlmConfigurationError(RuntimeError):
    """Raised when live LLM drafting is requested without provider settings."""


class LlmProviderError(RuntimeError):
    """Raised when the configured LLM provider does not return a usable draft."""


def _required_setting(value: str | None, name: str) -> str:
    if value is None or not value.strip():
        raise LlmConfigurationError(f"{name} is required for live LLM drafts")
    return value.strip()


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _extract_chat_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise LlmProviderError("LLM provider returned a non-object response")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LlmProviderError("LLM provider response did not include choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LlmProviderError("LLM provider response choice is invalid")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise LlmProviderError("LLM provider response did not include a message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LlmProviderError("LLM provider returned an empty draft")
    return content.strip()


async def generate_reversing_llm_draft(
    snapshot: dict, client: httpx.AsyncClient | None = None
) -> str:
    """Generate a DB reversing spec with a configured chat-completions provider."""

    return await _generate_llm_draft(
        prompt=generate_reversing_llm_prompt(snapshot),
        system_content=(
            "You write concise database reverse-engineering specifications "
            "from schema metadata. Do not invent facts."
        ),
        client=client,
    )


async def generate_index_design_llm_draft(
    snapshot: dict, client: httpx.AsyncClient | None = None
) -> str:
    """Generate table/index design guidance with a configured LLM provider."""

    return await _generate_llm_draft(
        prompt=generate_index_design_llm_prompt(snapshot),
        system_content=(
            "You write concise PostgreSQL table and index design guidance "
            "from schema metadata and workload evidence. Do not invent facts."
        ),
        client=client,
    )


async def _generate_llm_draft(
    *,
    prompt: str,
    system_content: str,
    client: httpx.AsyncClient | None,
) -> str:
    base_url = _required_setting(settings.llm_api_base_url, "LLM_API_BASE_URL")
    api_key = _required_setting(settings.llm_api_key, "LLM_API_KEY")
    model = _required_setting(settings.llm_model, "LLM_MODEL")
    request_json = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
    try:
        try:
            response = await client.post(
                _chat_completions_url(base_url),
                headers=headers,
                json=request_json,
            )
        except httpx.HTTPError as exc:
            raise LlmProviderError("LLM provider request failed") from exc
        if response.status_code >= 400:
            raise LlmProviderError(
                f"LLM provider request failed with HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise LlmProviderError("LLM provider returned invalid JSON") from exc
        return _extract_chat_content(payload)
    finally:
        if owns_client:
            await client.aclose()
