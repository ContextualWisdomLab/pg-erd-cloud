"""Repository contracts for exact production coverage enforcement in CI."""

from __future__ import annotations

from pathlib import Path


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_CI_WORKFLOW = _REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def test_backend_ci_enforces_complete_app_statement_and_branch_coverage() -> None:
    """The protected backend gate must measure the complete production package."""

    workflow = _CI_WORKFLOW.read_text(encoding="utf-8")
    assert "pytest -q --cov=app --cov-branch" in workflow
    assert "--cov-report=term-missing" in workflow
    assert "--cov-fail-under=100" in workflow


def test_backend_ci_does_not_run_an_unmeasured_plain_pytest_gate() -> None:
    """A plain pytest command must not substitute for the required coverage gate."""

    workflow = _CI_WORKFLOW.read_text(encoding="utf-8")
    assert "run: pytest -q\n" not in workflow
