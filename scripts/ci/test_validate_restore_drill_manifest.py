from __future__ import annotations

import importlib.util
import pathlib
from typing import Any

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "validate_restore_drill_manifest.py"


def load_validator() -> Any:
    assert SCRIPT.is_file(), "restore drill manifest validator script is missing"
    spec = importlib.util.spec_from_file_location("validate_restore_drill_manifest", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def valid_manifest() -> dict[str, Any]:
    return {
        "drill_id": "restore-drill-2026-07-02-staging",
        "drill_date": "2026-07-02",
        "environment": "staging-restore",
        "operator": "SRE on-call",
        "release_version": "v2026.07.02-commercial-candidate",
        "commit_sha": "41f8b014f68813ba50fb9dca8dfdad280920fe2c",
        "backup_artifact": {
            "path": "backups/pg-erd-cloud-20260702T000000Z.dump",
            "sha256": "a" * 64,
            "created_at": "2026-07-02T00:00:00Z",
        },
        "restore_target": {
            "postgres_image": "postgres:16-alpine@sha256:64b8bc2e6b2bdab4f0ce8019e9f8d71bc7f32b81a9a6ecb3f3d36cb4e5be1000",
            "database": "erd_restore",
            "isolated": True,
        },
        "app_secret_source": "vault://customer-acme/pg-erd-cloud/app-secret",
        "alembic_current": "0004_billing_event",
        "expected_alembic_revision": "0004_billing_event",
        "healthz": {"path": "/healthz", "ok": True},
        "smoke_tests": {
            "authenticated_project_list": True,
            "share_link_lookup": True,
            "share_link_revoke_or_expiry": True,
            "sql_export": True,
            "support_bundle_redaction": True,
        },
        "timings_minutes": {"backup": 7, "restore": 12, "application_smoke": 9},
        "evidence_links": [
            "https://github.com/ContextualWisdomLab/pg-erd-cloud/issues/415",
            "docs/operations/backup-restore.md",
        ],
        "status": "passed",
    }


def write_manifest(path: pathlib.Path, payload: dict[str, Any]) -> pathlib.Path:
    import json

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_valid_restore_drill_manifest_passes(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    manifest = write_manifest(tmp_path / "restore-drill.json", valid_manifest())

    validator.validate_manifest(manifest)


def test_main_validates_explicit_restore_drill_path(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    manifest = write_manifest(tmp_path / "restore-drill.customer.json", valid_manifest())

    assert validator.main([str(manifest)]) == 0


def test_missing_explicit_restore_drill_path_fails(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    missing = tmp_path / "missing-restore-drill.json"

    with pytest.raises(AssertionError, match="does not exist"):
        validator.main([str(missing)])


def test_missing_required_smoke_test_fails(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    payload = valid_manifest()
    del payload["smoke_tests"]["share_link_revoke_or_expiry"]
    manifest = write_manifest(tmp_path / "restore-drill.json", payload)

    with pytest.raises(AssertionError, match="smoke_tests.share_link_revoke_or_expiry"):
        validator.validate_manifest(manifest)


def test_example_manifest_is_required_by_main(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    validator = load_validator()
    manifest_dir = tmp_path / "restore-drills"
    manifest_dir.mkdir()
    monkeypatch.setattr(validator, "DRILL_DIR", manifest_dir)

    with pytest.raises(AssertionError, match="restore-drill.example.json is required"):
        validator.main([])
