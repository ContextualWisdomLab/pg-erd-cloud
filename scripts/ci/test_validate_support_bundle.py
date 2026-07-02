from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
from typing import Any

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "validate_support_bundle.py"


def load_validator() -> Any:
    assert SCRIPT.is_file(), "support bundle validator script is missing"
    spec = importlib.util.spec_from_file_location("validate_support_bundle", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def valid_bundle() -> dict[str, Any]:
    return json.loads(
        (ROOT / "docs" / "operations" / "support-bundles" / "support-bundle.example.json")
        .read_text(encoding="utf-8")
    )


def write_bundle(path: pathlib.Path, payload: dict[str, Any]) -> pathlib.Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_valid_support_bundle_manifest_passes(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    manifest = write_bundle(tmp_path / "support-bundle.json", valid_bundle())

    validator.validate_bundle(manifest)


def test_raw_metadata_must_be_redacted(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    payload = valid_bundle()
    payload["support_account_summary"]["metadata"] = {"api_key": "sk_live_secret"}
    manifest = write_bundle(tmp_path / "support-bundle.json", payload)

    with pytest.raises(AssertionError, match="support_account_summary.metadata"):
        validator.validate_bundle(manifest)


def test_backend_log_secret_assignment_fails(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    payload = valid_bundle()
    payload["backend_error_log_tail"] = ["api_key=sk_live_secret"]
    manifest = write_bundle(tmp_path / "support-bundle.json", payload)

    with pytest.raises(AssertionError, match="backend_error_log_tail"):
        validator.validate_bundle(manifest)


def test_example_manifest_is_required_by_main(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validator = load_validator()
    manifest_dir = tmp_path / "support-bundles"
    manifest_dir.mkdir()
    monkeypatch.setattr(validator, "BUNDLE_DIR", manifest_dir)

    with pytest.raises(AssertionError, match="example support bundle manifest"):
        validator.main()


def test_missing_compose_digest_fails_when_compose_exists(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    payload = copy.deepcopy(valid_bundle())
    payload["deployment"]["compose_prod"]["sha256"] = None
    manifest = write_bundle(tmp_path / "support-bundle.json", payload)

    with pytest.raises(AssertionError, match="compose_prod.sha256"):
        validator.validate_bundle(manifest)
