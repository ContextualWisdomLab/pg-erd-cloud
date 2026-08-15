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

    with pytest.raises(AssertionError, match="workflow expression"):
        _validate(unsafe)


@pytest.mark.parametrize(
    "expression",
    (
        "${{ inputs.unreviewed_input }}",
        "${{ inputs['unreviewed_input'] }}",
        "${{ github.event.inputs['unreviewed_input'] }}",
        "${{ github['event']['inputs']['unreviewed_input'] }}",
        "${{ github.event['inputs'].unreviewed_input }}",
        "${{ toJSON(inputs) }}",
        "${{ toJSON(github.event.inputs) }}",
        "${{ format('{{{0}}}', inputs.unreviewed_input) }}",
        "${{ github.sha }}",
    ),
)
def test_validator_rejects_unknown_workflow_expression(
    expression: str,
) -> None:
    """Reject every expression outside the reviewed expression allowlist."""

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    unsafe = workflow.replace(
        "          COMMIT_COUNT_INPUT: ${{ inputs.commit_count }}",
        "          COMMIT_COUNT_INPUT: ${{ inputs.commit_count }}\n"
        f"          EXTRA_INPUT: {expression}",
        1,
    )

    with pytest.raises(AssertionError, match="workflow expression"):
        _validate(unsafe)


def test_validator_rejects_multiline_workflow_expression() -> None:
    """Reject folded expressions that the line-oriented verifier cannot parse."""

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    unsafe = workflow.replace(
        "          COMMIT_COUNT_INPUT: ${{ inputs.commit_count }}",
        "          COMMIT_COUNT_INPUT: ${{ inputs.commit_count }}\n"
        "          EXTRA_INPUT: >-\n"
        "            ${{ toJSON(\n"
        "            inputs) }}",
        1,
    )

    with pytest.raises(AssertionError, match="workflow expression"):
        _validate(unsafe)


def test_validator_rejects_approved_expression_at_new_location() -> None:
    """Reject an approved spelling copied into another step or mapping."""

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    unsafe = workflow.replace(
        "      - name: Initialize CodeQL",
        "      - name: Unreviewed input consumer\n"
        "        env:\n"
        "          BRANCH_INPUT: ${{ inputs.branch }}\n"
        "        run: echo unreviewed\n\n"
        "      - name: Initialize CodeQL",
        1,
    )

    with pytest.raises(AssertionError, match="workflow expression"):
        _validate(unsafe)


@pytest.mark.parametrize(
    "unsafe",
    (
        "permissions:\n  contents: read\n  security-events: write",
        "    permissions:\n      contents: read\n      security-events: write",
    ),
)
def test_validator_limits_security_event_write_to_analysis_job(
    unsafe: str,
) -> None:
    """Reject CodeQL upload authority at workflow or enumerate-job scope."""

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    original = (
        "permissions:\n  contents: read"
        if unsafe.startswith("permissions:")
        else "    permissions:\n      contents: read"
    )
    mutated = workflow.replace(original, unsafe, 1)

    with pytest.raises(AssertionError, match="security-events: write"):
        _validate(mutated)


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
