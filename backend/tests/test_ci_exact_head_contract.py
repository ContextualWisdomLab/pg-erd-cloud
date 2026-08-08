"""Contracts for validating the literal pull-request head in CI."""

from __future__ import annotations

from pathlib import Path


CI_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
EXACT_HEAD_REF = (
    "ref: ${{ github.event_name == 'pull_request' "
    "&& github.event.pull_request.head.sha || github.sha }}"
)


def test_ci_checkouts_validate_the_exact_pull_request_head() -> None:
    """Require both CI jobs to test the PR head instead of the synthetic merge ref."""

    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert workflow.count(EXACT_HEAD_REF) == 2
