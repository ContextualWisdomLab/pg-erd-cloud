"""Regression tests for exact-head and coverage enforcement in repository CI."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"
CHECKOUT_MARKER = "      - name: Checkout\n"


def _ci_workflow() -> str:
    """Return the checked-out CI workflow as UTF-8 text."""
    return CI_WORKFLOW_PATH.read_text(encoding="utf-8")


def test_each_checkout_uses_exact_head_without_persisted_credentials() -> None:
    """Require both CI jobs to validate the literal PR head without saved auth."""
    workflow = _ci_workflow()
    checkout_sections = workflow.split(CHECKOUT_MARKER)[1:]

    assert len(checkout_sections) == 2
    for section in checkout_sections:
        checkout_to_setup = section.split("      - name: Setup ", 1)[0]
        assert "persist-credentials: false" in checkout_to_setup
        assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in checkout_to_setup
        assert "      - name: Verify exact pull-request head" in checkout_to_setup
        assert "if: github.event_name == 'pull_request'" in checkout_to_setup
        assert "EXPECTED_HEAD_SHA: ${{ github.event.pull_request.head.sha }}" in checkout_to_setup
        assert 'run: test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD_SHA"' in checkout_to_setup


def test_backend_ci_enforces_exact_auth_statement_and_branch_coverage() -> None:
    """Require exact coverage for the security boundary owned by this PR."""
    workflow = _ci_workflow()

    assert (
        "pytest -q --cov=app.auth --cov-branch --cov-fail-under=100" in workflow
    )


def test_frontend_ci_uses_the_repository_test_contract() -> None:
    """Keep this backend-only security PR out of frontend coverage policy."""
    workflow = _ci_workflow()

    assert "run: npm run test" in workflow
    assert "run: npm run coverage" not in workflow
