from __future__ import annotations

import importlib.util
import json
import pathlib
from typing import Any

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "validate_commercial_release_approval.py"


def load_validator() -> Any:
    assert SCRIPT.is_file(), "commercial release approval validator script is missing"
    spec = importlib.util.spec_from_file_location("validate_commercial_release_approval", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def valid_manifest() -> dict[str, Any]:
    return json.loads(
        (ROOT / "docs" / "legal" / "release-approvals" / "release-approval.example.json")
        .read_text(encoding="utf-8")
    )


def write_manifest(path: pathlib.Path, payload: dict[str, Any]) -> pathlib.Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_main_validates_explicit_release_approval_path(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    manifest = write_manifest(tmp_path / "release-approval.customer.json", valid_manifest())

    assert validator.main([str(manifest)]) == 0


def test_missing_explicit_release_approval_path_fails(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    missing = tmp_path / "missing-release-approval.json"

    with pytest.raises(AssertionError, match="does not exist"):
        validator.main([str(missing)])


def test_release_approval_rejects_placeholder_text(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    payload = valid_manifest()
    payload["legal_approver"] = "TBD"
    manifest = write_manifest(tmp_path / "release-approval.customer.json", payload)

    with pytest.raises(AssertionError, match="legal_approver"):
        validator.validate_manifest(manifest)
