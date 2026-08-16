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
    """Add only the adaptive request assertion for the RED commit."""
    replace_once(
        TEST_PATH,
        '        seen["model"] = body["model"]\n        seen["messages"] = body["messages"]',
        '        seen["model"] = body["model"]\n        seen["orchestration_mode"] = body["orchestration_mode"]\n        seen["messages"] = body["messages"]',
    )
    replace_once(
        TEST_PATH,
        '    assert seen["model"] == "test-model"\n    messages = seen["messages"]',
        '    assert seen["model"] == "test-model"\n    assert seen["orchestration_mode"] == "auto"\n    messages = seen["messages"]',
    )


def implement() -> None:
    """Delegate live draft execution topology to adaptive orchestration."""
    replace_once(
        SOURCE_PATH,
        '    request_json = {\n        "model": model,\n        "messages": [',
        '    request_json = {\n        "model": model,\n        "orchestration_mode": "auto",\n        "messages": [',
    )

    replace_once(
        DOC_PATH,
        'exposes exactly that interface (`/v1/chat/completions`) while routing,\ndelegating, verifying, and synthesizing across a pool of model agents.\n\nSo the integration is **configuration only — no code change**.',
        'exposes exactly that interface (`/v1/chat/completions`) while routing,\ndelegating, verifying, and synthesizing across a pool of model agents.\n\nEvery pg-erd-cloud draft request explicitly includes `orchestration_mode: auto`.\nThe orchestration plane therefore owns model/provider selection, workflow depth,\nverification, fallback, and known-price optimization. Quality sufficiency is the\nfirst constraint; cost is minimized among quality-sufficient execution paths.\nMissing price metadata is classified as unpriced rather than free.',
    )

    replace_once(
        CHANGELOG_PATH,
        '# Changelog\n',
        '# Changelog\n\n## Unreleased\n\n### Changed\n\n- Live reverse-engineering and index-design drafts now explicitly request contextual-orchestrator `auto` mode, allowing the orchestration plane to satisfy quality requirements and then minimize known cost instead of relying on an implicit or single-model default.\n',
    )

    ADR_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ADR_PATH.exists():
        raise SystemExit(f"refusing to overwrite {ADR_PATH}")
    ADR_PATH.write_text(
        """# ADR-0001: Adaptive contextual-orchestrator mode is the LLM-draft default

- Status: Accepted
- Date: 2026-08-16

## Context

pg-erd-cloud delegated live reverse-engineering and index-design drafts to an OpenAI-compatible endpoint but omitted an explicit orchestration mode. Contextual-orchestrator currently interprets omission as adaptive behavior, yet the consumer contract did not make that requirement reviewable or prevent future drift to fixed single-model routing.

## Decision

Every live LLM-draft request includes `orchestration_mode: "auto"`.

Contextual-orchestrator owns model/provider selection, test-time compute, workflow depth, verification, fallback, and known-price optimization. Quality sufficiency is the first constraint; cost is minimized among execution paths that satisfy it. Missing or untrusted price metadata is classified as unpriced, not free.

pg-erd-cloud continues to own schema evidence, prompt construction, credential boundaries, response parsing, and fail-closed API errors. Explicit route or conduct modes are reserved for controlled ablation or a documented incident override and are not product defaults.

## Consequences

Simple drafts may still use one worker when adaptive policy finds that sufficient. Complex or high-risk database guidance may use deeper orchestration without changing pg-erd-cloud's API.

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
