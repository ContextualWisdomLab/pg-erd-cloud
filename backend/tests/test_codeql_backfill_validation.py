"""Regression tests for the manual CodeQL backfill workflow contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/codeql-backfill.yml"
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts/ci/validate_codeql_backfill.py"

_SPEC = importlib.util.spec_from_file_location(
    "validate_codeql_backfill",
    VALIDATOR_PATH,
)
assert _SPEC is not None
assert _SPEC.loader is not None
_VALIDATOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_VALIDATOR)


def _validate(workflow: str) -> None:
    _VALIDATOR.validate_workflow(workflow)


def test_current_codeql_backfill_workflow_passes_static_contract() -> None:
    """Accept the reviewed workflow without special test-only exceptions."""

    _validate(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "expression",
    (
        "${{ inputs.branch }}",
        "${{  inputs.branch  }}",
        "${{ inputs.commit_count }}",
        "${{ github.event.inputs.branch }}",
    ),
)
def test_validator_rejects_unapproved_input_expression_use(
    expression: str,
) -> None:
    """Reject new shell interpolation even when assignment spelling changes."""

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    unsafe = workflow.replace(
        "          set -euo pipefail",
        f'          echo "{expression}"\n          set -euo pipefail',
        1,
    )

    with pytest.raises(AssertionError, match="workflow input expression"):
        _validate(unsafe)


def test_validator_requires_previous_branch_alias_rejection() -> None:
    """Keep @{-n} aliases from passing validation with their raw refspec form."""

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    unsafe = workflow.replace(
        'if ! normalized_branch="$(git check-ref-format --branch "${branch}")"; then',
        'if ! git check-ref-format --branch "${branch}" >/dev/null; then',
        1,
    ).replace(
        "\n          if [[ \"${normalized_branch}\" != \"${branch}\" ]]; then\n"
        "            echo \"branch aliases are not accepted\" >&2\n"
        "            exit 1\n"
        "          fi\n",
        "\n",
        1,
    )

    with pytest.raises(AssertionError, match="normalized branch"):
        _validate(unsafe)
