"""Regression tests for exact-head and coverage enforcement in repository CI."""

from pathlib import Path
import re


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def _ci_workflow() -> str:
    """Return the checked-out CI workflow as UTF-8 text."""
    return CI_WORKFLOW_PATH.read_text(encoding="utf-8")


def test_each_checkout_uses_exact_head_without_persisted_credentials() -> None:
    """Require both CI jobs to validate the literal PR head without saved auth."""
    workflow = _ci_workflow()
    checkout_blocks = re.findall(
        r"(?ms)^      - name: Checkout\n"
        r"        uses: actions/checkout@[0-9a-f]{40}.*?\n"
        r"        with:\n"
        r"(?P<inputs>(?:          .+\n)+?)"
        r"\n      - name: Verify exact pull-request head\n"
        r"        if: github.event_name == 'pull_request'\n"
        r"        env:\n"
        r"          EXPECTED_HEAD_SHA: \$\{\{ github\.event\.pull_request\.head\.sha \}\}\n"
        r'        run: test "\$\(git rev-parse HEAD\)" = "\$EXPECTED_HEAD_SHA"\n'
        r"\n      - name: Setup (?:Python|Node)",
        workflow,
    )

    assert len(checkout_blocks) == 2
    for inputs in checkout_blocks:
        assert "persist-credentials: false" in inputs
        assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in inputs


def test_backend_ci_enforces_full_statement_and_branch_coverage() -> None:
    """Require backend CI to fail below the repository's 100% coverage contract."""
    workflow = _ci_workflow()

    assert "pytest -q --cov=app --cov-branch --cov-fail-under=100" in workflow
