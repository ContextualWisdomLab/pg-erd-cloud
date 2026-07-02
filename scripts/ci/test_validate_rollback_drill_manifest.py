from __future__ import annotations

import importlib.util
import json
import pathlib
from typing import Any

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "validate_rollback_drill_manifest.py"


def load_validator() -> Any:
    assert SCRIPT.is_file(), "rollback drill manifest validator script is missing"
    spec = importlib.util.spec_from_file_location("validate_rollback_drill_manifest", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def valid_manifest() -> dict[str, Any]:
    return json.loads(
        (ROOT / "docs" / "operations" / "rollback-drills" / "rollback-drill.example.json")
        .read_text(encoding="utf-8")
    )


def write_manifest(path: pathlib.Path, payload: dict[str, Any]) -> pathlib.Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_valid_rollback_drill_manifest_passes(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    manifest = write_manifest(tmp_path / "rollback-drill.json", valid_manifest())

    validator.validate_manifest(manifest)


def test_main_validates_explicit_rollback_drill_path(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    manifest = write_manifest(tmp_path / "rollback-drill.customer.json", valid_manifest())

    assert validator.main([str(manifest)]) == 0


def test_missing_explicit_rollback_drill_path_fails(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    missing = tmp_path / "missing-rollback-drill.json"

    with pytest.raises(AssertionError, match="does not exist"):
        validator.main([str(missing)])


def test_missing_required_smoke_test_fails(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    payload = valid_manifest()
    del payload["smoke_tests"]["share_link_lookup"]
    manifest = write_manifest(tmp_path / "rollback-drill.json", payload)

    with pytest.raises(AssertionError, match="smoke_tests.share_link_lookup"):
        validator.validate_manifest(manifest)


def test_post_revision_must_match_target(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    payload = valid_manifest()
    payload["rollback"]["post_rollback_revision"] = "0005_llm_draft_usage_event"
    manifest = write_manifest(tmp_path / "rollback-drill.json", payload)

    with pytest.raises(AssertionError, match="post_rollback_revision"):
        validator.validate_manifest(manifest)


def test_example_manifest_is_required_by_main(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    validator = load_validator()
    manifest_dir = tmp_path / "rollback-drills"
    manifest_dir.mkdir()
    monkeypatch.setattr(validator, "DRILL_DIR", manifest_dir)

    with pytest.raises(AssertionError, match="rollback-drill.example.json is required"):
        validator.main([])
