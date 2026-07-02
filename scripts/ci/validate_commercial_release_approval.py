#!/usr/bin/env python3
"""Validate commercial release approval manifests."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
APPROVAL_DIR = ROOT / "docs" / "legal" / "release-approvals"
EXAMPLE_NAME = "release-approval.example.json"

REQUIRED_STRING_FIELDS = (
    "release_version",
    "commit_sha",
    "sale_motion",
    "contract_plan",
    "billing_method",
    "approval_date",
    "product_owner",
    "legal_approver",
    "security_approver",
    "support_approver",
    "support_channel",
    "vulnerability_owner",
)

REQUIRED_LIST_FIELDS = (
    "data_processing_scope",
    "subprocessors",
    "unsupported_scope",
    "customer_notice",
)

REQUIRED_DOCUMENTS = (
    "terms",
    "privacy",
    "sla",
    "license_billing",
    "security_policy",
    "incident_response",
    "backup_restore",
    "migration_rollback",
    "alert_thresholds",
)

PLACEHOLDER_RE = re.compile(r"\b(tbd|todo|fixme|pending|placeholder)\b|[<>]", re.IGNORECASE)
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_text(value: Any, field: str) -> str:
    require(isinstance(value, str), f"{field} must be a string")
    text = value.strip()
    require(text, f"{field} must not be blank")
    require(PLACEHOLDER_RE.search(text) is None, f"{field} must not contain placeholders")
    return text


def require_text_list(value: Any, field: str) -> None:
    require(isinstance(value, list), f"{field} must be a list")
    require(len(value) > 0, f"{field} must not be empty")
    for index, item in enumerate(value):
        require_text(item, f"{field}[{index}]")


def validate_manifest(path: pathlib.Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path.relative_to(ROOT)} is invalid JSON: {exc}") from exc

    require(isinstance(payload, dict), f"{path.relative_to(ROOT)} must contain a JSON object")

    for field in REQUIRED_STRING_FIELDS:
        require_text(payload.get(field), field)

    require(SHA_RE.match(payload["commit_sha"]) is not None, "commit_sha must be 7-40 lowercase hex characters")
    try:
        dt.date.fromisoformat(payload["approval_date"])
    except ValueError as exc:
        raise AssertionError("approval_date must use YYYY-MM-DD") from exc

    documents = payload.get("documents")
    require(isinstance(documents, dict), "documents must be an object")
    for key in REQUIRED_DOCUMENTS:
        value = require_text(documents.get(key), f"documents.{key}")
        document_path = ROOT / value
        require(document_path.is_file(), f"documents.{key} does not exist: {value}")

    for field in REQUIRED_LIST_FIELDS:
        require_text_list(payload.get(field), field)


def main() -> int:
    require(APPROVAL_DIR.is_dir(), "release approval manifest directory is missing")

    manifests = sorted(APPROVAL_DIR.glob("*.json"))
    require(manifests, "at least the example release approval manifest is required")

    example = APPROVAL_DIR / EXAMPLE_NAME
    require(example in manifests, f"{EXAMPLE_NAME} is required")

    for manifest in manifests:
        validate_manifest(manifest)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validate_commercial_release_approval.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
