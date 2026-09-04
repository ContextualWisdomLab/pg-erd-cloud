"""Contracts for repository-owned GitHub Actions workflows."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIRECTORY = REPOSITORY_ROOT / ".github" / "workflows"
CENTRAL_REQUIRED_WORKFLOWS = {
    "codeql-pr.yml",
    "noema-review.yml",
    "opencode-review.yml",
    "pr-review-merge-scheduler.yml",
    "security-scan.yml",
    "strix.yml",
    "sast-semgrep.yml",
}


def test_local_workflows_keep_central_ownership_and_pr_concurrency() -> None:
    """Keep central gates local-free and retire superseded CI heads per PR."""
    workflow_paths = sorted(WORKFLOW_DIRECTORY.glob("*.yml"))
    workflow_names = {workflow_path.name for workflow_path in workflow_paths}
    workflow_text = "\n".join(
        workflow_path.read_text(encoding="utf-8") for workflow_path in workflow_paths
    )
    ci_workflow = (WORKFLOW_DIRECTORY / "ci.yml").read_text(encoding="utf-8")
    backfill_workflow = (WORKFLOW_DIRECTORY / "codeql-backfill.yml").read_text(
        encoding="utf-8"
    )

    assert workflow_names.isdisjoint(CENTRAL_REQUIRED_WORKFLOWS)
    assert "schedule:" not in workflow_text
    assert "sleep " not in workflow_text
    assert "workflow_dispatch:" in backfill_workflow
    assert "pull_request:" not in backfill_workflow
    assert "push:" not in backfill_workflow
    assert (
        "group: ci-${{ github.repository }}-"
        "${{ github.event.pull_request.number || github.run_id }}" in ci_workflow
    )
    assert (
        "cancel-in-progress: ${{ github.event_name == 'pull_request' }}"
        in ci_workflow
    )
