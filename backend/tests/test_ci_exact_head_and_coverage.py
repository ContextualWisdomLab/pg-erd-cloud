"""Contracts for exact-head CI and mandatory production coverage."""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def _ci_source() -> str:
    """Return the repository-owned CI workflow as inert text."""
    return CI_WORKFLOW.read_text(encoding="utf-8")


def test_every_checkout_is_exact_head_and_does_not_persist_credentials() -> None:
    """Bind executable backend/frontend tests to the PR SHA without retained auth."""
    workflow = _ci_source()
    checkout_blocks = re.findall(
        r"(?ms)^      - name: Checkout\n"
        r"        uses: actions/checkout@[0-9a-f]{40}.*?\n"
        r"        with:\n"
        r"(?P<inputs>(?:          .+\n)+?)"
        r"\n      - name: Setup (?:Python|Node)",
        workflow,
    )
    assert len(checkout_blocks) == 2, "backend and frontend need scoped Checkout steps"
    for inputs in checkout_blocks:
        assert "persist-credentials: false" in inputs
        assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in inputs


def test_backend_pytest_enforces_full_production_branch_coverage() -> None:
    """Fail CI unless backend application statements and branches remain fully covered."""
    workflow = _ci_source()
    assert (
        "pytest -q --cov=app --cov-branch --cov-fail-under=100 "
        "--cov-report=term-missing"
        in workflow
    )
