#!/usr/bin/env python3
"""Build a tamper-evident index for external commercial sale evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = ROOT / "scripts" / "ci" / "commercial_readiness_audit.py"

EVIDENCE_ARGS = (
    ("signed_release_approval", "release_approval", "--release-approval"),
    ("customer_restore_drill", "restore_drill", "--restore-drill"),
    ("customer_rollback_drill", "rollback_drill", "--rollback-drill"),
    ("support_bundle_evidence", "support_bundle", "--support-bundle"),
    ("real_billing_provider_catalog", "billing_provider_catalog", "--billing-provider-catalog"),
)


def _load_audit_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "commercial_readiness_audit",
        AUDIT_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load commercial readiness audit: {AUDIT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _relative(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _resolve(path: pathlib.Path) -> pathlib.Path:
    return path if path.is_absolute() else ROOT / path


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def explicit_evidence_paths_from_args(args: argparse.Namespace) -> dict[str, list[pathlib.Path]]:
    return {
        evidence_id: list(getattr(args, attr_name))
        for evidence_id, attr_name, _flag in EVIDENCE_ARGS
    }


def build_index(explicit_evidence_paths: dict[str, list[pathlib.Path]]) -> dict[str, Any]:
    audit = _load_audit_module()
    report = audit.generate_report(explicit_evidence_paths)
    gates_by_id = {gate["id"]: gate for gate in report["real_evidence_gates"]}
    evidence_entries: list[dict[str, Any]] = []

    for evidence_id, paths in explicit_evidence_paths.items():
        gate = gates_by_id.get(evidence_id, {})
        for raw_path in paths:
            path = _resolve(raw_path)
            exists = path.is_file()
            entry: dict[str, Any] = {
                "id": evidence_id,
                "label": gate.get("label"),
                "required_for": gate.get("required_for"),
                "path": _relative(path),
                "exists": exists,
                "gate_status": gate.get("status"),
                "explicit_validator_passed": gate.get("explicit_validator_passed"),
                "explicit_sample_markers": gate.get("explicit_sample_markers", []),
            }
            if exists:
                entry.update(
                    {
                        "size_bytes": path.stat().st_size,
                        "sha256": _sha256(path),
                    }
                )
            evidence_entries.append(entry)

    return {
        "index_schema_version": 1,
        "generated_at": report["generated_at"],
        "sale_ready": report["sale_ready"],
        "decision": report["decision"],
        "schema_ready": report["schema_ready"],
        "real_evidence_ready": report["real_evidence_ready"],
        "review_queue_is_blocker": report["review_queue_is_blocker"],
        "queued_checks_are_blocker": report["queued_checks_are_blocker"],
        "evidence": evidence_entries,
        "sale_blockers": report["sale_blockers"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a JSON index for external commercial evidence paths. "
            "The index records file identity and readiness gates without copying "
            "evidence contents."
        )
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output JSON path. Use '-' for stdout. Default: '-'.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Return exit code 0 even when sale_ready is false; useful during evidence intake.",
    )
    for _evidence_id, attr_name, flag in EVIDENCE_ARGS:
        parser.add_argument(
            flag,
            action="append",
            default=[],
            dest=attr_name,
            type=pathlib.Path,
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    index = build_index(explicit_evidence_paths_from_args(args))
    payload = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output == "-":
        print(payload)
    else:
        output_path = pathlib.Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    if not args.allow_incomplete and not index["sale_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
