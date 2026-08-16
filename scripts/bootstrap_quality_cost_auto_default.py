#!/usr/bin/env python3
"""Create the test-first adaptive contextual-orchestrator draft patch."""

from __future__ import annotations

import sys
from pathlib import Path

TEST_PATH = Path("backend/tests/test_reversing_llm.py")
SOURCE_PATH = Path("backend/app/spec/llm.py")
DOC_PATH = Path("docs/llm-orchestrator-integration.md")
CHANGELOG_PATH = Path("CHANGELOG.md")
ADR_PATH = Path("docs/adr/0001-adaptive-contextual-orchestrator-default.md")


def replace_once(path: Path, old: str, new: str) -> None:
    """Replace exactly one source fragment or fail closed."""
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def write_test() -> None:
    """Add the adaptive gateway contract and generic-provider compatibility test."""
    replace_once(
        TEST_PATH,
        '    monkeypatch.setattr(settings, "llm_model", "test-model")\n    seen: dict[str, object] = {}',
        '    monkeypatch.setattr(settings, "llm_model", "contextual-orchestrator")\n    seen: dict[str, object] = {}',
    )
    replace_once(
        TEST_PATH,
        '        seen["model"] = body["model"]\n        seen["messages"] = body["messages"]',
        '        seen["model"] = body["model"]\n        seen["orchestration_mode"] = body["orchestration_mode"]\n        seen["messages"] = body["messages"]',
    )
    replace_once(
        TEST_PATH,
        '    assert seen["model"] == "test-model"\n    messages = seen["messages"]',
        '    assert seen["model"] == "contextual-orchestrator"\n    assert seen["orchestration_mode"] == "auto"\n    messages = seen["messages"]',
    )
    marker = '\n\n@pytest.mark.asyncio\nasync def test_generate_reversing_llm_draft_requires_configuration('
    compatibility_test = '''

@pytest.mark.asyncio
async def test_generate_reversing_llm_draft_keeps_generic_provider_payload_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_api_base_url", "https://llm.example/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "generic-model")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen["body"] = body
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Draft"}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await generate_reversing_llm_draft(_snapshot(), client=client) == "Draft"

    body = seen["body"]
    assert isinstance(body, dict)
    assert "orchestration_mode" not in body
'''
    replace_once(TEST_PATH, marker, compatibility_test + marker)


def implement() -> None:
    """Delegate contextual-orchestrator topology without breaking generic providers."""
    replace_once(
        SOURCE_PATH,
        '    request_json = {\n        "model": model,\n        "messages": [',
        '    request_json = {\n        "model": model,\n        **({"orchestration_mode": "auto"} if model == "contextual-orchestrator" else {}),\n        "messages": [',
    )

    replace_once(
        DOC_PATH,
        'exposes exactly that interface (`/v1/chat/completions`) while routing,\ndelegating, verifying, and synthesizing across a pool of model agents.\n\nSo the integration is **configuration only — no code change**.',
        'exposes exactly that interface (`/v1/chat/completions`) while routing,\ndelegating, verifying, and synthesizing across a pool of model agents.\n\nWhen `LLM_MODEL=contextual-orchestrator`, pg-erd-cloud explicitly includes\n`orchestration_mode: auto`. The orchestration plane therefore owns model/provider\nselection, workflow depth, verification, fallback, and known-price optimization.\nQuality sufficiency is the first constraint; cost is minimized among\nquality-sufficient execution paths. Missing price metadata is classified as\nunpriced rather than free. Other OpenAI-compatible model identifiers retain the\ngeneric provider payload and receive no orchestration-only field.',
    )

    replace_once(
        CHANGELOG_PATH,
        '# Changelog\n',
        '# Changelog\n\n## Unreleased\n\n### Changed\n\n- Live drafts configured with `LLM_MODEL=contextual-orchestrator` now explicitly request adaptive `auto` mode, while generic OpenAI-compatible providers retain their original payload contract.\n',
    )

    ADR_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ADR_PATH.exists():
        raise SystemExit(f"refusing to overwrite {ADR_PATH}")
    ADR_PATH.write_text(
        """# ADR-0001: Adaptive contextual-orchestrator mode is the LLM-draft default

- Status: Accepted
- Date: 2026-08-16

## Context

pg-erd-cloud can call either contextual-orchestrator or another OpenAI-compatible provider. It omitted an explicit orchestration mode, so the contextual gateway's adaptive requirement was not reviewable. Sending an orchestration-only field to every provider would, however, violate the generic compatibility contract.

## Decision

When and only when `LLM_MODEL` is exactly `contextual-orchestrator`, every live LLM-draft request includes `orchestration_mode: "auto"`.

Contextual-orchestrator owns model/provider selection, test-time compute, workflow depth, verification, fallback, and known-price optimization. Quality sufficiency is the first constraint; cost is minimized among execution paths that satisfy it. Missing or untrusted price metadata is classified as unpriced, not free.

Other model identifiers receive the unchanged generic OpenAI-compatible request. pg-erd-cloud continues to own schema evidence, prompt construction, credential boundaries, response parsing, and fail-closed API errors. Explicit route or conduct modes are reserved for controlled ablation or a documented incident override and are not product defaults.

## Consequences

Contextual-orchestrator deployments obtain an explicit adaptive default without breaking direct providers that reject unknown fields. Simple drafts may still use one worker when adaptive policy finds that sufficient; complex or high-risk database guidance may use deeper orchestration.

## References

Omidvar, H., & Akhlaghi, V. (2026). *A communication-theoretic framework for LLM agents: Cost-aware adaptive reliability* [Preprint]. arXiv. https://doi.org/10.48550/arXiv.2605.09121

Tang, Y., Cetin, E., Xu, J., Sun, Q., Nielsen, S., Richard, V., Goda, H., Tymchenko, I., Nguyen, N., Lee, H., Ashiga, M., Kotyan, S., Kuroki, S., & Clanuwat, T. (2026). *Sakana Fugu technical report* [Technical report]. arXiv. https://doi.org/10.48550/arXiv.2606.21228
""",
        encoding="utf-8",
    )


def main() -> None:
    """Run one bounded bootstrap phase."""
    if len(sys.argv) != 2 or sys.argv[1] not in {"test", "implement"}:
        raise SystemExit("usage: bootstrap_quality_cost_auto_default.py test|implement")
    if sys.argv[1] == "test":
        write_test()
    else:
        implement()


if __name__ == "__main__":
    main()
