#!/usr/bin/env python3
"""Report whether commercial release evidence is example-only or sale-ready."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]

VALIDATORS = (
    ("release_approval_schema", "scripts/ci/validate_commercial_release_approval.py"),
    ("billing_provider_catalog_schema", "scripts/ci/validate_billing_provider_catalog.py"),
    ("support_bundle_schema", "scripts/ci/validate_support_bundle.py"),
    ("onprem_package_schema", "scripts/ci/validate_onprem_package.py"),
    ("restore_drill_schema", "scripts/ci/validate_restore_drill_manifest.py"),
    ("rollback_drill_schema", "scripts/ci/validate_rollback_drill_manifest.py"),
)

EVIDENCE_VALIDATORS = {
    "signed_release_approval": "scripts/ci/validate_commercial_release_approval.py",
    "customer_restore_drill": "scripts/ci/validate_restore_drill_manifest.py",
    "customer_rollback_drill": "scripts/ci/validate_rollback_drill_manifest.py",
    "support_bundle_evidence": "scripts/ci/validate_support_bundle.py",
    "real_billing_provider_catalog": "scripts/ci/validate_billing_provider_catalog.py",
}

SAMPLE_TEXT_MARKERS = (
    (
        "reserved_example_domain",
        re.compile(r"\bexample\.(?:com|org|net)\b", re.IGNORECASE),
    ),
    (
        "fake_commit_sha",
        re.compile(r"\b0123456789abcdef0123456789abcdef01234567\b", re.IGNORECASE),
    ),
    (
        "single_character_sha256",
        re.compile(r"\b([0-9a-f])\1{63}\b", re.IGNORECASE),
    ),
    (
        "customer_acme_placeholder",
        re.compile(r"\bcustomer-acme\b", re.IGNORECASE),
    ),
)

REAL_EVIDENCE_RULES = (
    {
        "id": "signed_release_approval",
        "label": "Signed commercial release approval",
        "required_for": "general_sale",
        "directory": "docs/legal/release-approvals",
        "pattern": "*.json",
        "example_names": {"release-approval.example.json"},
        "no_go_reason": "Only the example release approval manifest is present.",
    },
    {
        "id": "customer_restore_drill",
        "label": "Customer or staging restore drill evidence",
        "required_for": "on_premises_sale",
        "directory": "docs/operations/restore-drills",
        "pattern": "*.json",
        "example_names": {"restore-drill.example.json"},
        "no_go_reason": "Only the example restore drill manifest is present.",
    },
    {
        "id": "customer_rollback_drill",
        "label": "Customer or staging rollback drill evidence",
        "required_for": "on_premises_sale",
        "directory": "docs/operations/rollback-drills",
        "pattern": "*.json",
        "example_names": {"rollback-drill.example.json"},
        "no_go_reason": "Only the example rollback drill manifest is present.",
    },
    {
        "id": "support_bundle_evidence",
        "label": "Redacted customer support bundle evidence",
        "required_for": "paid_pilot_support",
        "directory": "docs/operations/support-bundles",
        "pattern": "*.json",
        "example_names": {"support-bundle.example.json"},
        "no_go_reason": "Only the example support bundle manifest is present.",
    },
    {
        "id": "real_billing_provider_catalog",
        "label": "Real billing provider catalog",
        "required_for": "paid_billing",
        "directory": "docs/operations",
        "pattern": "billing-provider-catalog*.json",
        "example_names": {"billing-provider-catalog.example.json"},
        "no_go_reason": "Only the example billing provider catalog is present.",
    },
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _relative(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _run_validator(script_path: str, paths: list[pathlib.Path] | None = None) -> dict[str, Any]:
    command = [sys.executable, script_path]
    if paths:
        command.extend(str(path) for path in paths)
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "script": script_path,
        "paths": [_relative(path) for path in paths or []],
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stderr": result.stderr.strip(),
    }


def _sample_markers_in_value(value: Any, field_path: str) -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = f"{field_path}.{key}" if field_path else key
            findings.extend(_sample_markers_in_value(child, child_path))
        return findings
    if isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_sample_markers_in_value(child, f"{field_path}[{index}]"))
        return findings
    if isinstance(value, str):
        for marker_id, pattern in SAMPLE_TEXT_MARKERS:
            if pattern.search(value):
                findings.append(f"{field_path}: {marker_id}")
    return findings


def _sample_markers(path: pathlib.Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [f"{_relative(path)}: unreadable_json"]
    return [
        f"{_relative(path)}:{finding}"
        for finding in _sample_markers_in_value(payload, "")
    ]


def _real_evidence_gate(
    rule: dict[str, Any],
    explicit_paths: list[pathlib.Path],
    explicit_validator_passed: bool | None,
    explicit_sample_markers: list[str],
    repo_validator_passed: bool | None,
    repo_sample_markers: list[str],
) -> dict[str, Any]:
    directory = ROOT / str(rule["directory"])
    example_names = set(rule["example_names"])
    files = sorted(directory.glob(str(rule["pattern"]))) if directory.is_dir() else []
    example_files = [path for path in files if path.name in example_names]
    real_files = [path for path in files if path.name not in example_names]
    explicit_real_paths = [path for path in explicit_paths if path.name not in example_names]
    explicit_example_paths = [path for path in explicit_paths if path.name in example_names]
    has_valid_repo_evidence = (
        bool(real_files)
        and repo_validator_passed is True
        and not repo_sample_markers
    )
    has_valid_explicit_evidence = (
        bool(explicit_real_paths)
        and explicit_validator_passed is True
        and not explicit_sample_markers
    )
    status = "ready"
    if repo_validator_passed is False:
        status = "no_go"
    elif repo_sample_markers:
        status = "no_go"
    elif explicit_paths and explicit_validator_passed is False:
        status = "no_go"
    elif explicit_sample_markers:
        status = "no_go"
    elif not has_valid_repo_evidence and not has_valid_explicit_evidence:
        status = "no_go"

    no_go_reason = None
    if status != "ready":
        if repo_validator_passed is False:
            no_go_reason = "Repository evidence files failed the required validator."
        elif repo_sample_markers:
            no_go_reason = "Repository evidence files still contain example or synthetic evidence markers."
        elif explicit_paths and explicit_validator_passed is False:
            no_go_reason = "Explicit evidence paths failed the required validator."
        elif explicit_sample_markers:
            no_go_reason = "Explicit evidence paths still contain example or synthetic evidence markers."
        elif explicit_example_paths and not explicit_real_paths:
            no_go_reason = "Explicit evidence paths use example manifest names."
        else:
            no_go_reason = rule["no_go_reason"]
    return {
        "id": rule["id"],
        "label": rule["label"],
        "required_for": rule["required_for"],
        "status": status,
        "real_evidence_files": [_relative(path) for path in [*real_files, *explicit_real_paths]],
        "repo_real_evidence_files": [_relative(path) for path in real_files],
        "repo_validator_passed": repo_validator_passed,
        "repo_sample_markers": repo_sample_markers,
        "explicit_evidence_files": [_relative(path) for path in explicit_real_paths],
        "explicit_example_files": [_relative(path) for path in explicit_example_paths],
        "explicit_validator_passed": explicit_validator_passed,
        "explicit_sample_markers": explicit_sample_markers,
        "example_files": [_relative(path) for path in example_files],
        "no_go_reason": no_go_reason,
    }


def generate_report(explicit_evidence_paths: dict[str, list[pathlib.Path]] | None = None) -> dict[str, Any]:
    explicit_evidence_paths = explicit_evidence_paths or {}
    validator_results = [
        {"id": gate_id, **_run_validator(script_path)}
        for gate_id, script_path in VALIDATORS
    ]
    explicit_validator_passed: dict[str, bool | None] = {}
    explicit_sample_markers: dict[str, list[str]] = {}
    repo_validator_passed: dict[str, bool | None] = {}
    repo_sample_markers: dict[str, list[str]] = {}
    for rule in REAL_EVIDENCE_RULES:
        evidence_id = str(rule["id"])
        directory = ROOT / str(rule["directory"])
        example_names = set(rule["example_names"])
        files = sorted(directory.glob(str(rule["pattern"]))) if directory.is_dir() else []
        real_files = [path for path in files if path.name not in example_names]
        if not real_files:
            repo_validator_passed[evidence_id] = None
            repo_sample_markers[evidence_id] = []
            continue
        result = {
            "id": f"repo_{evidence_id}",
            **_run_validator(EVIDENCE_VALIDATORS[evidence_id], real_files),
        }
        validator_results.append(result)
        repo_validator_passed[evidence_id] = result["passed"]
        repo_sample_markers[evidence_id] = [
            marker
            for path in real_files
            for marker in _sample_markers(path)
        ]

    for evidence_id, paths in explicit_evidence_paths.items():
        if not paths:
            explicit_validator_passed[evidence_id] = None
            explicit_sample_markers[evidence_id] = []
            continue
        result = {
            "id": f"explicit_{evidence_id}",
            **_run_validator(EVIDENCE_VALIDATORS[evidence_id], paths),
        }
        validator_results.append(result)
        explicit_validator_passed[evidence_id] = result["passed"]
        explicit_sample_markers[evidence_id] = [
            marker
            for path in paths
            for marker in _sample_markers(path)
        ]

    schema_ready = all(result["passed"] for result in validator_results)
    evidence_gates = [
        _real_evidence_gate(
            rule,
            explicit_evidence_paths.get(str(rule["id"]), []),
            explicit_validator_passed.get(str(rule["id"])),
            explicit_sample_markers.get(str(rule["id"]), []),
            repo_validator_passed.get(str(rule["id"])),
            repo_sample_markers.get(str(rule["id"]), []),
        )
        for rule in REAL_EVIDENCE_RULES
    ]
    evidence_ready = all(gate["status"] == "ready" for gate in evidence_gates)
    sale_ready = schema_ready and evidence_ready
    return {
        "generated_at": _utc_now(),
        "sale_ready": sale_ready,
        "schema_ready": schema_ready,
        "real_evidence_ready": evidence_ready,
        "validator_results": validator_results,
        "real_evidence_gates": evidence_gates,
        "decision": "ready_for_sale" if sale_ready else "not_ready_for_sale",
        "review_queue_is_blocker": False,
        "queued_checks_are_blocker": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a commercial readiness report for pg-erd-cloud.",
    )
    parser.add_argument(
        "--output",
        help="Optional output JSON path. Use '-' to print to stdout.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the report is not ready_for_sale.",
    )
    parser.add_argument(
        "--release-approval",
        action="append",
        default=[],
        type=pathlib.Path,
        help="Signed release approval manifest path to validate as real sale evidence.",
    )
    parser.add_argument(
        "--restore-drill",
        action="append",
        default=[],
        type=pathlib.Path,
        help="Customer or staging restore drill manifest path to validate as real sale evidence.",
    )
    parser.add_argument(
        "--rollback-drill",
        action="append",
        default=[],
        type=pathlib.Path,
        help="Customer or staging rollback drill manifest path to validate as real sale evidence.",
    )
    parser.add_argument(
        "--support-bundle",
        action="append",
        default=[],
        type=pathlib.Path,
        help="Redacted customer or staging support bundle path to validate as real sale evidence.",
    )
    parser.add_argument(
        "--billing-provider-catalog",
        action="append",
        default=[],
        type=pathlib.Path,
        help="Real billing provider catalog manifest path to validate as real sale evidence.",
    )
    return parser


def _explicit_evidence_paths_from_args(args: argparse.Namespace) -> dict[str, list[pathlib.Path]]:
    return {
        "signed_release_approval": list(args.release_approval),
        "customer_restore_drill": list(args.restore_drill),
        "customer_rollback_drill": list(args.rollback_drill),
        "support_bundle_evidence": list(args.support_bundle),
        "real_billing_provider_catalog": list(args.billing_provider_catalog),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = generate_report(_explicit_evidence_paths_from_args(args))
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output == "-":
        print(payload)
    elif args.output:
        output_path = pathlib.Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    if args.strict and not report["sale_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
