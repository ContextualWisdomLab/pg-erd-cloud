"""Contracts for exact-head CI and mandatory production coverage."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def _ci_source() -> str:
    """Return the repository-owned CI workflow as inert text."""
    return CI_WORKFLOW.read_text(encoding="utf-8")


def _checkout_inputs(workflow: str) -> list[str]:
    """Return each named Checkout step body up to the following workflow step."""
    marker = "      - name: Checkout\n"
    blocks: list[str] = []
    for remainder in workflow.split(marker)[1:]:
        block, separator, _tail = remainder.partition("\n      - name: ")
        assert separator, "each Checkout step must be followed by another named step"
        blocks.append(block)
    return blocks


def test_every_checkout_is_exact_head_and_does_not_persist_credentials() -> None:
    """Bind executable backend/frontend tests to the PR SHA without retained auth."""
    checkout_blocks = _checkout_inputs(_ci_source())
    assert len(checkout_blocks) == 2, "backend and frontend need scoped Checkout steps"
    for block in checkout_blocks:
        assert "uses: actions/checkout@" in block
        assert "persist-credentials: false" in block
        assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in block


def test_backend_pytest_enforces_full_production_branch_coverage() -> None:
    """Fail CI unless backend application statements and branches remain fully covered."""
    workflow = _ci_source()
    assert (
        "pytest -q --cov=app --cov-branch --cov-fail-under=100 "
        "--cov-report=term-missing"
        in workflow
    )
