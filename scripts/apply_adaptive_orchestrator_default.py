#!/usr/bin/env python3
"""Add explicit contextual-orchestrator auto mode to the LLM draft request."""

from __future__ import annotations

import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source_path = root / "backend" / "app" / "spec" / "llm.py"
doc_path = root / "docs" / "llm-orchestrator-integration.md"
adr_path = root / "docs" / "adr" / "0010-adaptive-contextual-orchestrator-default.md"

source = source_path.read_text(encoding="utf-8")
if "orchestration_mode" not in source:
    transformations = [
        (
            r'(?P<indent>[ \t]*)(?P<quote>["\'])model(?P=quote)\s*:\s*(?P<value>[^,\n}]+),\s*\n(?P=indent)(?P<message_quote>["\'])messages(?P=message_quote)\s*:',
            lambda match: (
                f"{match.group('indent')}{match.group('quote')}model{match.group('quote')}:"
                f"{match.group('value')},\n"
                f"{match.group('indent')}{match.group('quote')}orchestration_mode{match.group('quote')}: "
                f"{match.group('quote')}auto{match.group('quote')},\n"
                f"{match.group('indent')}{match.group('message_quote')}messages{match.group('message_quote')}:"
            ),
        ),
        (
            r'(?P<prefix>["\']model["\']\s*:\s*[^,}]+,\s*)(?P<messages>["\']messages["\']\s*:)',
            lambda match: (
                f"{match.group('prefix')}\"orchestration_mode\": \"auto\", "
                f"{match.group('messages')}"
            ),
        ),
        (
            r'(?P<indent>[ \t]*)model=(?P<value>[^,\n)]+),\s*\n(?P=indent)messages=',
            lambda match: (
                f"{match.group('indent')}model={match.group('value')},\n"
                f"{match.group('indent')}extra_body={{\"orchestration_mode\": \"auto\"}},\n"
                f"{match.group('indent')}messages="
            ),
        ),
    ]
    for pattern, replacement in transformations:
        source, count = re.subn(pattern, replacement, source, count=1)
        if count == 1:
            break
    else:
        raise RuntimeError("could not locate the model/messages request construction")
source_path.write_text(source, encoding="utf-8")

if doc_path.exists():
    doc = doc_path.read_text(encoding="utf-8")
    paragraph = (
        "\nThe production request also sends `orchestration_mode: \"auto\"`. "
        "This delegates route, independent verification, conducted workflow, "
        "provider choice, and known-cost tie-breaking to contextual-orchestrator "
        "instead of forcing a single worker in pg-erd-cloud.\n"
    )
    if paragraph.strip() not in doc:
        heading = "## Point pg-erd-cloud at the orchestrator\n"
        if heading not in doc:
            raise RuntimeError("orchestrator integration heading was not found")
        doc = doc.replace(heading, heading + paragraph, 1)
        doc_path.write_text(doc, encoding="utf-8")

adr_path.parent.mkdir(parents=True, exist_ok=True)
if not adr_path.exists():
    adr_path.write_text(
        '''# ADR-0010: LLM draft requests use contextual-orchestrator auto

- Status: Accepted
- Date: 2026-08-16

## Context

pg-erd-cloud generates bounded LLM draft material through the organization gateway,
but an implicit or model-only request does not make execution-policy ownership
reviewable. The ERD product must not choose one provider/model or a fixed multi-agent
shape for every reverse-engineering and index-design task.

## Decision

The LLM request explicitly selects `orchestration_mode: "auto"` while retaining the
`contextual-orchestrator` model alias. The orchestration plane chooses the
quality-sufficient route, verification, or conducted workflow and minimizes known
cost only after capability constraints. Unknown price metadata is not treated as
free.

pg-erd-cloud retains prompt construction, database authorization, schema semantics,
strict response handling, and user-visible draft review. Explicit fixed modes remain
controlled orchestration experiments, not application defaults.

## References

Omidvar, H., & Akhlaghi, V. (2026). *A communication-theoretic framework for LLM agents: Cost-aware adaptive reliability* [Preprint]. arXiv. https://doi.org/10.48550/arXiv.2605.09121

Tang, Y., Cetin, E., Xu, J., Sun, Q., Nielsen, S., Richard, V., Goda, H., Tymchenko, I., Nguyen, N., Lee, H., Ashiga, M., Kotyan, S., Kuroki, S., & Clanuwat, T. (2026). *Sakana Fugu technical report* [Technical report]. arXiv. https://doi.org/10.48550/arXiv.2606.21228
''',
        encoding="utf-8",
    )

changelog_path = root / "CHANGELOG.md"
if changelog_path.exists():
    changelog = changelog_path.read_text(encoding="utf-8")
    entry = (
        "- LLM draft requests now explicitly use contextual-orchestrator `auto` "
        "rather than a consumer-owned single-model default.\n"
    )
    if entry not in changelog:
        marker = "## Unreleased\n"
        if marker in changelog:
            changelog = changelog.replace(marker, marker + "\n### Changed\n\n" + entry, 1)
        else:
            changelog = "## Unreleased\n\n### Changed\n\n" + entry + "\n" + changelog
        changelog_path.write_text(changelog, encoding="utf-8")
