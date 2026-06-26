#!/usr/bin/env python3
"""Normalize OpenCode review output into the strict approval-gate contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


STRUCTURAL_FAILURE_PHRASES = (
    "structural exploration was not possible",
    "structural exploration not possible",
    "structural exploration is not required",
    "structural exploration not required",
    "structural analysis is not required",
    "structural analysis not required",
    "structural review is not required",
    "structural review not required",
    "no structural exploration required",
    "no structural analysis required",
    "no structural review required",
    "structural exploration is unnecessary",
    "structural analysis is unnecessary",
    "structural review is unnecessary",
    "changed files could not be inspected",
    "source files could not be inspected",
    "required files could not be inspected",
    "could not access changed files",
    "could not access the changed files",
    "could not access source files",
    "could not access the source files",
    "could not access required files",
    "could not access required evidence",
    "evidence was truncated",
    "truncated evidence",
)

STRUCTURAL_FAILURE_PATTERNS = (
    re.compile(
        r"\b(?:could not|cannot|can't|unable to)\s+"
        r"(?:inspect|access|review)\s+(?:the\s+)?"
        r"(?:changed|source|required)\s+files?\b"
    ),
    re.compile(
        r"\b(?:changed|source|required)\s+files?\s+"
        r"(?:could not|cannot|can't|were not|was not)\s+"
        r"(?:be\s+)?(?:inspected|accessed|reviewed)\b"
    ),
    re.compile(
        r"\b(?:structural\s+(?:exploration|analysis|review))\s+"
        r"(?:was\s+)?(?:unavailable|incomplete|blocked|not possible)\b"
    ),
)


def admits_missing_structural_review(reason: str, summary: str) -> bool:
    combined = f"{reason}\n{summary}".casefold()
    return any(phrase in combined for phrase in STRUCTURAL_FAILURE_PHRASES) or any(
        pattern.search(combined) for pattern in STRUCTURAL_FAILURE_PATTERNS
    )


def check_structural_approval(control_file: Path) -> int:
    try:
        value = json.loads(control_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read OpenCode control JSON: {exc}", file=sys.stderr)
        return 65

    if not isinstance(value, dict):
        print("NO_CONCLUSION", file=sys.stderr)
        return 4

    if value.get("result") == "APPROVE" and admits_missing_structural_review(
        str(value.get("reason", "")),
        str(value.get("summary", "")),
    ):
        print("NO_CONCLUSION", file=sys.stderr)
        return 4

    return 0


def valid_control(
    value: Any,
    *,
    expected_head_sha: str,
    expected_run_id: str,
    expected_run_attempt: str,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    if value.get("head_sha") != expected_head_sha:
        return None
    if value.get("run_id") != expected_run_id:
        return None
    if value.get("run_attempt") != expected_run_attempt:
        return None

    result = value.get("result")
    if result not in {"APPROVE", "REQUEST_CHANGES"}:
        return None

    if not isinstance(value.get("reason"), str) or not value["reason"].strip():
        return None
    if not isinstance(value.get("summary"), str) or not value["summary"].strip():
        return None
    reason = value["reason"].strip()
    summary = value["summary"].strip()

    findings = value.get("findings")
    if findings is None and result == "APPROVE":
        findings = []
    if not isinstance(findings, list):
        return None
    if result == "APPROVE" and findings:
        return None
    if result == "REQUEST_CHANGES" and not findings:
        return None
    if result == "APPROVE" and admits_missing_structural_review(reason, summary):
        return None

    required_finding_fields = (
        "path",
        "severity",
        "title",
        "problem",
        "root_cause",
        "fix_direction",
        "regression_test_direction",
        "suggested_diff",
    )
    for finding in findings:
        if not isinstance(finding, dict):
            return None
        if not isinstance(finding.get("line"), int) or finding["line"] <= 0:
            return None
        for field in required_finding_fields:
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                return None

    return {
        "head_sha": value["head_sha"],
        "run_id": value["run_id"],
        "run_attempt": value["run_attempt"],
        "result": result,
        "reason": reason,
        "summary": summary,
        "findings": findings,
    }


def iter_json_objects(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    values: list[Any] = []

    try:
        values.append(json.loads(text))
    except json.JSONDecodeError:
        # OpenCode exports may contain prose around the JSON control object.
        pass

    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        values.append(value)

    return values


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--check-structural-approval":
        return check_structural_approval(Path(argv[2]))

    if len(argv) != 5:
        print(
            "usage: opencode_review_normalize_output.py "
            "<expected_head_sha> <expected_run_id> <expected_run_attempt> <output_file>\n"
            "   or: opencode_review_normalize_output.py --check-structural-approval <control_json_file>",
            file=sys.stderr,
        )
        return 64

    expected_head_sha, expected_run_id, expected_run_attempt, output_file_arg = argv[1:]
    output_file = Path(output_file_arg)
    try:
        output_text = output_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read OpenCode output file: {exc}", file=sys.stderr)
        return 65

    for value in iter_json_objects(output_text):
        control = valid_control(
            value,
            expected_head_sha=expected_head_sha,
            expected_run_id=expected_run_id,
            expected_run_attempt=expected_run_attempt,
        )
        if control is None:
            continue

        normalized_json = json.dumps(control, separators=(",", ":"), ensure_ascii=False)
        output_file.write_text(
            "\n".join(
                [
                    (
                        "<!-- opencode-review-gate "
                        f"head_sha={expected_head_sha} "
                        f"run_id={expected_run_id} "
                        f"run_attempt={expected_run_attempt} -->"
                    ),
                    "",
                    "<!-- opencode-review-control-v1",
                    normalized_json,
                    "-->",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return 0

    print("NO_CONCLUSION", file=sys.stderr)
    return 4


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
