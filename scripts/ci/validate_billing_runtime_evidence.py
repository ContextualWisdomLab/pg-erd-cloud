#!/usr/bin/env python3
"""Validate redacted billing runtime evidence manifests."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
FORBIDDEN_RAW_VALUE_KEYS = {
    "actual_value",
    "expected_value",
    "raw_value",
    "secret_value",
    "webhook_secret",
    "signature_secret",
}
FORBIDDEN_VALUE_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "sk_live_",
    "whsec_",
    "xoxb-",
    "AKIA",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def display_path(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def require_text(value: Any, field: str) -> str:
    require(isinstance(value, str), f"{field} must be a string")
    text = value.strip()
    require(text, f"{field} must not be blank")
    return text


def require_mapping(value: Any, field: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{field} must be an object")
    return value


def require_bool(value: Any, field: str) -> bool:
    require(isinstance(value, bool), f"{field} must be a boolean")
    return value


def require_sha256(value: Any, field: str) -> str:
    text = require_text(value, field)
    require(SHA256_RE.match(text) is not None, f"{field} must be a 64-character hex digest")
    return text


def _scan_forbidden_values(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            lowered = key.lower()
            child_path = f"{path}.{key}" if path else key
            require(
                lowered not in FORBIDDEN_RAW_VALUE_KEYS,
                f"{child_path} must not include raw values",
            )
            _scan_forbidden_values(raw_value, child_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_forbidden_values(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        for marker in FORBIDDEN_VALUE_MARKERS:
            require(marker not in value, f"{path} contains forbidden marker {marker}")


def validate_environment_entry(entry: Any, index: int) -> dict[str, Any]:
    item = require_mapping(entry, f"required_environment[{index}]")
    name = require_text(item.get("name"), f"required_environment[{index}].name")
    require(
        ENV_NAME_RE.match(name) is not None,
        f"required_environment[{index}].name is invalid",
    )
    sensitive = require_bool(
        item.get("sensitive"),
        f"required_environment[{index}].sensitive",
    )
    configured = require_bool(
        item.get("configured"),
        f"required_environment[{index}].configured",
    )
    matches_catalog = require_bool(
        item.get("matches_catalog"),
        f"required_environment[{index}].matches_catalog",
    )
    require(
        item.get("value_redacted") is True,
        f"required_environment[{index}].value_redacted must be true",
    )
    require_sha256(
        item.get("expected_sha256"),
        f"required_environment[{index}].expected_sha256",
    )

    if sensitive:
        secret_reference_configured = require_bool(
            item.get("secret_reference_configured"),
            f"required_environment[{index}].secret_reference_configured",
        )
        raw_secret_material_observed = require_bool(
            item.get("raw_secret_material_observed"),
            f"required_environment[{index}].raw_secret_material_observed",
        )
        require(
            "actual_sha256" not in item,
            f"required_environment[{index}] must not hash sensitive actual values",
        )
        if secret_reference_configured:
            require_sha256(
                item.get("actual_reference_sha256"),
                f"required_environment[{index}].actual_reference_sha256",
            )
        else:
            require(
                "actual_reference_sha256" not in item,
                f"required_environment[{index}].actual_reference_sha256 requires a configured secret reference",
            )
        if raw_secret_material_observed:
            require(
                matches_catalog is False,
                f"required_environment[{index}] raw secret material cannot match catalog",
            )
    else:
        require(
            "secret_reference_configured" not in item,
            f"required_environment[{index}] non-secret entry must not include secret_reference_configured",
        )
        require(
            "raw_secret_material_observed" not in item,
            f"required_environment[{index}] non-secret entry must not include raw_secret_material_observed",
        )
        if configured:
            require_sha256(
                item.get("actual_sha256"),
                f"required_environment[{index}].actual_sha256",
            )
        else:
            require(
                "actual_sha256" not in item,
                f"required_environment[{index}].actual_sha256 requires configured=true",
            )
    return item


def validate_evidence(path: pathlib.Path) -> None:
    require(path.is_file(), f"billing runtime evidence does not exist: {display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{display_path(path)} is invalid JSON: {exc}") from exc
    require_mapping(payload, display_path(path))
    _scan_forbidden_values(payload, "")

    require(payload.get("evidence_schema_version") == 1, "evidence_schema_version must be 1")
    generated_at = require_text(payload.get("generated_at"), "generated_at")
    try:
        dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssertionError("generated_at must be ISO-8601") from exc

    catalog = require_mapping(payload.get("catalog"), "catalog")
    require_text(catalog.get("path"), "catalog.path")
    require_sha256(catalog.get("sha256"), "catalog.sha256")
    require_text(catalog.get("catalog_version"), "catalog.catalog_version")
    require_text(catalog.get("provider"), "catalog.provider")
    effective_date = require_text(catalog.get("effective_date"), "catalog.effective_date")
    try:
        dt.date.fromisoformat(effective_date)
    except ValueError as exc:
        raise AssertionError("catalog.effective_date must use YYYY-MM-DD") from exc

    runtime_environment = require_mapping(
        payload.get("runtime_environment"),
        "runtime_environment",
    )
    require(runtime_environment.get("source") == "env_file", "runtime_environment.source must be env_file")
    require_text(runtime_environment.get("path"), "runtime_environment.path")
    require_sha256(runtime_environment.get("sha256"), "runtime_environment.sha256")
    duplicate_required_keys = runtime_environment.get("duplicate_required_keys")
    require(
        isinstance(duplicate_required_keys, list),
        "runtime_environment.duplicate_required_keys must be a list",
    )
    for index, key in enumerate(duplicate_required_keys):
        require_text(key, f"runtime_environment.duplicate_required_keys[{index}]")

    entries = payload.get("required_environment")
    require(isinstance(entries, list) and entries, "required_environment must be a non-empty list")
    parsed_entries = [
        validate_environment_entry(entry, index)
        for index, entry in enumerate(entries)
    ]
    names = [entry["name"] for entry in parsed_entries]
    require(len(names) == len(set(names)), "required_environment names must be unique")

    blockers = payload.get("runtime_blockers")
    require(isinstance(blockers, list), "runtime_blockers must be a list")
    for index, blocker in enumerate(blockers):
        blocker_payload = require_mapping(blocker, f"runtime_blockers[{index}]")
        require_text(blocker_payload.get("type"), f"runtime_blockers[{index}].type")
        require_text(blocker_payload.get("name"), f"runtime_blockers[{index}].name")
        require_text(blocker_payload.get("reason"), f"runtime_blockers[{index}].reason")

    summary = require_mapping(payload.get("summary"), "summary")
    required_count = summary.get("required_count")
    configured_count = summary.get("configured_required_count")
    require(isinstance(required_count, int), "summary.required_count must be an integer")
    require(isinstance(configured_count, int), "summary.configured_required_count must be an integer")
    require(required_count == len(parsed_entries), "summary.required_count must match required_environment")
    require(
        configured_count == sum(1 for entry in parsed_entries if entry["configured"]),
        "summary.configured_required_count must match configured entries",
    )
    for field in (
        "all_required_environment_configured",
        "all_non_secret_values_match_catalog",
        "all_secret_references_match_catalog",
        "raw_secret_material_observed",
        "sale_ready_runtime",
    ):
        require_bool(summary.get(field), f"summary.{field}")

    calculated_ready = not blockers
    require(
        summary["sale_ready_runtime"] is calculated_ready,
        "summary.sale_ready_runtime must match runtime_blockers",
    )
    if summary["sale_ready_runtime"]:
        require(
            all(entry["configured"] and entry["matches_catalog"] for entry in parsed_entries),
            "sale_ready_runtime requires every entry to be configured and catalog-matched",
        )
        require(
            not any(entry.get("raw_secret_material_observed") is True for entry in parsed_entries),
            "sale_ready_runtime forbids raw secret material",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate generated billing runtime evidence JSON files."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=pathlib.Path,
        help="Billing runtime evidence JSON path(s).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for evidence in args.paths:
        validate_evidence(evidence)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validate_billing_runtime_evidence.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
