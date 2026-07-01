#!/usr/bin/env python3
"""Static contract checks for the CodeQL SAST backfill workflow."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "codeql-backfill.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")

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

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validate_codeql_backfill.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
