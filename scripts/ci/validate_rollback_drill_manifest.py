#!/usr/bin/env python3
"""Validate on-premises migration rollback drill evidence manifests."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
DRILL_DIR = ROOT / "docs" / "operations" / "rollback-drills"
EXAMPLE_NAME = "rollback-drill.example.json"

REQUIRED_STRING_FIELDS = (
    "drill_id",
    "environment",
    "operator",
    "release_version",
    "commit_sha",
    "migration_tool",
    "database",
)

REQUIRED_SMOKE_TESTS = (
    "authenticated_project_list",
    "snapshot_lookup",
    "share_link_lookup",
    "sql_export",
    "support_bundle_redaction",
)

REQUIRED_TIMINGS = ("dry_run_review", "rollback", "application_smoke")

PLACEHOLDER_RE = re.compile(r"\b(tbd|todo|fixme|pending|placeholder)\b|[<>]", re.IGNORECASE)
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[A-Za-z0-9_.:-]{2,128}$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


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


def require_revision(value: Any, field: str) -> str:
    text = require_text(value, field)
    require(REVISION_RE.match(text) is not None, f"{field} has invalid revision syntax")
    return text


def validate_manifest(path: pathlib.Path) -> None:
    require(path.is_file(), f"rollback drill manifest does not exist: {display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{display_path(path)} is invalid JSON: {exc}") from exc

    require(isinstance(payload, dict), f"{display_path(path)} must contain a JSON object")

    for field in REQUIRED_STRING_FIELDS:
        require_text(payload.get(field), field)

    require_iso_date(payload.get("drill_date"), "drill_date")
    require(payload["migration_tool"] == "alembic", "migration_tool must be alembic")
    require(SHA_RE.match(payload["commit_sha"]) is not None, "commit_sha must be 7-40 lowercase hex characters")
    require(payload.get("status") == "passed", "status must be passed")

    backup = require_object(payload.get("backup_artifact"), "backup_artifact")
    backup_path = require_text(backup.get("path"), "backup_artifact.path")
    require(backup_path.endswith(".dump"), "backup_artifact.path must reference a custom-format .dump file")
    backup_sha = require_text(backup.get("sha256"), "backup_artifact.sha256")
    require(SHA256_RE.match(backup_sha) is not None, "backup_artifact.sha256 must be 64 lowercase hex characters")
    require_iso_datetime(backup.get("created_at"), "backup_artifact.created_at")

    dry_run = require_object(payload.get("dry_run"), "dry_run")
    dry_run_command = require_text(dry_run.get("command"), "dry_run.command")
    require("alembic downgrade" in dry_run_command, "dry_run.command must run alembic downgrade")
    require("--sql" in dry_run_command, "dry_run.command must include --sql")
    dry_run_sha = require_text(dry_run.get("sql_sha256"), "dry_run.sql_sha256")
    require(SHA256_RE.match(dry_run_sha) is not None, "dry_run.sql_sha256 must be 64 lowercase hex characters")
    require_true(dry_run.get("reviewed"), "dry_run.reviewed")

    rollback = require_object(payload.get("rollback"), "rollback")
    rollback_command = require_text(rollback.get("command"), "rollback.command")
    require("alembic downgrade" in rollback_command, "rollback.command must run alembic downgrade")
    require("--sql" not in rollback_command, "rollback.command must execute rollback, not only generate SQL")
    pre_revision = require_revision(rollback.get("pre_rollback_revision"), "rollback.pre_rollback_revision")
    target_revision = require_revision(rollback.get("target_revision"), "rollback.target_revision")
    post_revision = require_revision(rollback.get("post_rollback_revision"), "rollback.post_rollback_revision")
    require(pre_revision != target_revision, "rollback target must differ from pre_rollback_revision")
    require(post_revision == target_revision, "post_rollback_revision must match target_revision")
    require_true(rollback.get("destructive_migration_reviewed"), "rollback.destructive_migration_reviewed")
    require_true(rollback.get("restore_fallback_available"), "rollback.restore_fallback_available")

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate on-premises rollback drill evidence manifests. With no paths, "
            "validates committed docs/operations/rollback-drills/*.json."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=pathlib.Path,
        help="Optional rollback drill JSON path(s) to validate directly.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.paths:
        for manifest in args.paths:
            validate_manifest(manifest)
        return 0

    require(DRILL_DIR.is_dir(), "rollback drill manifest directory is missing")

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
        print(f"validate_rollback_drill_manifest.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
