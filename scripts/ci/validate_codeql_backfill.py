#!/usr/bin/env python3
"""Static contract checks for the CodeQL SAST backfill workflow."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "codeql-backfill.yml"
INPUT_EXPRESSION = re.compile(
    r"\$\{\{\s*(?P<expression>"
    r"inputs\.(?:branch|commit_count)|github\.event\.inputs\.[^}\s]+"
    r")\s*\}\}"
)
ALLOWED_INPUT_EXPRESSION_LINES = {
    "inputs.branch": {
        "BRANCH_INPUT: ${{ inputs.branch }}",
        'ref: "refs/heads/${{ inputs.branch }}"',
    },
    "inputs.commit_count": {
        "COMMIT_COUNT_INPUT: ${{ inputs.commit_count }}",
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _validate_input_expressions(text: str) -> None:
    """Allow workflow-dispatch inputs only at reviewed non-shell boundaries."""

    observed = {expression: set() for expression in ALLOWED_INPUT_EXPRESSION_LINES}
    for line in text.splitlines():
        stripped = line.strip()
        for match in INPUT_EXPRESSION.finditer(line):
            expression = match.group("expression")
            require(
                not expression.startswith("github.event.inputs."),
                "unapproved workflow input expression: github.event.inputs.*",
            )
            allowed_lines = ALLOWED_INPUT_EXPRESSION_LINES.get(expression, set())
            require(
                stripped in allowed_lines,
                f"unapproved workflow input expression: {expression}",
            )
            observed[expression].add(stripped)

    for expression, allowed_lines in ALLOWED_INPUT_EXPRESSION_LINES.items():
        require(
            observed[expression] == allowed_lines,
            f"workflow input expression locations changed: {expression}",
        )


def validate_workflow(text: str) -> None:
    """Validate one complete CodeQL backfill workflow document."""

    require("workflow_dispatch:" in text, "workflow must be manual-only")
    require("branch:" in text, "branch input is required")
    require("commit_count:" in text, "commit_count input is required")
    require('default: "main"' in text, "branch default must remain main")
    require('default: "30"' in text, "commit_count default must remain 30")
    require("security-events: write" in text, "CodeQL upload permission is required")
    require("persist-credentials: false" in text, "checkout credentials must not persist")
    require("git rev-list --max-count" in text, "must enumerate recent commits")
    require("--first-parent" not in text, "must not skip non-first-parent commits")
    require("count > 127" in text, "commit_count must cap the workflow at 256 jobs")
    require("github/codeql-action/init@" in text, "must initialize CodeQL")
    require("github/codeql-action/analyze@" in text, "must upload CodeQL analysis")
    require('ref: "refs/heads/${{ inputs.branch }}"' in text, "analysis ref must target the requested branch")
    require("sha: ${{ matrix.commit }}" in text, "analysis SHA must use the selected commit")
    require(
        "BRANCH_INPUT: ${{ inputs.branch }}" in text,
        "branch input must enter the shell through env",
    )
    require(
        "COMMIT_COUNT_INPUT: ${{ inputs.commit_count }}" in text,
        "commit_count input must enter the shell through env",
    )
    require(
        'branch="${BRANCH_INPUT}"' in text,
        "shell must read the branch from its environment",
    )
    require(
        'count="${COMMIT_COUNT_INPUT}"' in text,
        "shell must read commit_count from its environment",
    )
    _validate_input_expressions(text)
    require(
        'normalized_branch="$(git check-ref-format --branch "${branch}")"'
        in text,
        "branch input must produce a normalized branch name",
    )
    require(
        'if [[ "${normalized_branch}" != "${branch}" ]]' in text,
        "normalized branch must equal the original input",
    )
    require(
        'source_ref="refs/heads/${branch}"' in text,
        "fetch source must be an explicit heads ref",
    )
    require(
        'tracking_ref="refs/remotes/origin/${branch}"' in text,
        "fetch destination must be an explicit remote-tracking ref",
    )
    require(
        'git fetch --no-tags --prune origin -- "${source_ref}:${tracking_ref}"'
        in text,
        "fetch must terminate options before the validated refspec",
    )
    require(
        'git fetch --no-tags --prune origin "${branch}"' not in text,
        "branch input must not remain an option-capable fetch argument",
    )
    require(
        '"origin/${branch}"' not in text,
        "revision enumeration must use the explicit tracking ref",
    )

    language_match = re.search(r"language:\s*\[(?P<languages>[^\]]+)\]", text)
    require(language_match is not None, "language matrix is required")
    languages = {
        item.strip().strip('"').strip("'")
        for item in language_match.group("languages").split(",")
    }
    require(
        languages == {"javascript-typescript", "python"},
        f"unexpected language matrix: {sorted(languages)}",
    )


def main() -> int:
    validate_workflow(WORKFLOW.read_text(encoding="utf-8"))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validate_codeql_backfill.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
