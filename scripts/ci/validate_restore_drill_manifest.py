#!/usr/bin/env python3
"""Validate on-premises restore drill evidence manifests."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
DRILL_DIR = ROOT / "docs" / "operations" / "restore-drills"
EXAMPLE_NAME = "restore-drill.example.json"

REQUIRED_STRING_FIELDS = (
    "drill_id",
    "environment",
    "operator",
    "release_version",
    "commit_sha",
    "app_secret_source",
    "alembic_current",
    "expected_alembic_revision",
)

REQUIRED_SMOKE_TESTS = (
    "authenticated_project_list",
    "share_link_lookup",
    "share_link_revoke_or_expiry",
    "sql_export",
    "support_bundle_redaction",
)

REQUIRED_TIMINGS = ("backup", "restore", "application_smoke")

PLACEHOLDER_RE = re.compile(r"\b(tbd|todo|fixme|pending|placeholder)\b|[<>]", re.IGNORECASE)
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_DIGEST_RE = re.compile(r"^postgres:16-alpine@sha256:[0-9a-f]{64}$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
SECRET_SOURCE_RE = re.compile(
    r"^(vault|aws-secretsmanager|azure-keyvault|gcp-secret-manager|sealed-secret|file|1password)://"
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
    require(PLACEHOLDER_RE.search(text) is None, f"{field} must not contain placeholders")
    return text


def require_object(value: Any, field: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{field} must be an object")
    return value


def require_iso_date(value: Any, field: str) -> None:
    text = require_text(value, field)
    try:
        dt.date.fromisoformat(text)
    except ValueError as exc:
        raise AssertionError(f"{field} must use YYYY-MM-DD") from exc


def require_iso_datetime(value: Any, field: str) -> None:
    text = require_text(value, field)
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssertionError(f"{field} must use ISO-8601 datetime") from exc


def require_true(value: Any, field: str) -> None:
    require(value is True, f"{field} must be true")


def require_positive_number(value: Any, field: str) -> None:
    require(isinstance(value, int | float), f"{field} must be a number")
    require(value > 0, f"{field} must be greater than zero")
    require(value <= 1440, f"{field} must be no more than 1440 minutes")


def validate_manifest(path: pathlib.Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{display_path(path)} is invalid JSON: {exc}") from exc

    require(isinstance(payload, dict), f"{display_path(path)} must contain a JSON object")

    for field in REQUIRED_STRING_FIELDS:
        require_text(payload.get(field), field)

    require_iso_date(payload.get("drill_date"), "drill_date")
    require(SHA_RE.match(payload["commit_sha"]) is not None, "commit_sha must be 7-40 lowercase hex characters")
    require(payload.get("status") == "passed", "status must be passed")
    require(
        payload["alembic_current"] == payload["expected_alembic_revision"],
        "alembic_current must match expected_alembic_revision",
    )
    require(
        SECRET_SOURCE_RE.match(payload["app_secret_source"]) is not None,
        "app_secret_source must identify a secret store or file URI, not raw secret material",
    )

    backup = require_object(payload.get("backup_artifact"), "backup_artifact")
    backup_path = require_text(backup.get("path"), "backup_artifact.path")
    require(backup_path.endswith(".dump"), "backup_artifact.path must reference a custom-format .dump file")
    backup_sha = require_text(backup.get("sha256"), "backup_artifact.sha256")
    require(SHA256_RE.match(backup_sha) is not None, "backup_artifact.sha256 must be 64 lowercase hex characters")
    require_iso_datetime(backup.get("created_at"), "backup_artifact.created_at")

    restore_target = require_object(payload.get("restore_target"), "restore_target")
    postgres_image = require_text(restore_target.get("postgres_image"), "restore_target.postgres_image")
    require(
        IMAGE_DIGEST_RE.match(postgres_image) is not None,
        "restore_target.postgres_image must pin postgres:16-alpine by sha256 digest",
    )
    require_text(restore_target.get("database"), "restore_target.database")
    require_true(restore_target.get("isolated"), "restore_target.isolated")

    healthz = require_object(payload.get("healthz"), "healthz")
    require(healthz.get("path") == "/healthz", "healthz.path must be /healthz")
    require_true(healthz.get("ok"), "healthz.ok")

    smoke_tests = require_object(payload.get("smoke_tests"), "smoke_tests")
    for field in REQUIRED_SMOKE_TESTS:
        require_true(smoke_tests.get(field), f"smoke_tests.{field}")

    timings = require_object(payload.get("timings_minutes"), "timings_minutes")
    for field in REQUIRED_TIMINGS:
        require_positive_number(timings.get(field), f"timings_minutes.{field}")

    evidence_links = payload.get("evidence_links")
    require(isinstance(evidence_links, list), "evidence_links must be a list")
    require(evidence_links, "evidence_links must not be empty")
    for index, value in enumerate(evidence_links):
        link = require_text(value, f"evidence_links[{index}]")
        if not URL_RE.match(link):
            require(not pathlib.PurePosixPath(link).is_absolute(), f"evidence_links[{index}] must be relative or http(s)")
            require((ROOT / link).exists(), f"evidence_links[{index}] does not exist: {link}")


def main() -> int:
    require(DRILL_DIR.is_dir(), "restore drill manifest directory is missing")

    manifests = sorted(DRILL_DIR.glob("*.json"))
    example = DRILL_DIR / EXAMPLE_NAME
    require(example in manifests, f"{EXAMPLE_NAME} is required")

    for manifest in manifests:
        validate_manifest(manifest)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validate_restore_drill_manifest.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
