from __future__ import annotations

import importlib.util
import json
import pathlib
from typing import Any

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER_SCRIPT = ROOT / "scripts" / "operations" / "build_billing_runtime_evidence.py"
VALIDATOR_SCRIPT = ROOT / "scripts" / "ci" / "validate_billing_runtime_evidence.py"
CATALOG = ROOT / "docs" / "operations" / "billing-provider-catalog.example.json"


def load_module(path: pathlib.Path, name: str) -> Any:
    assert path.is_file()
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_env(path: pathlib.Path) -> pathlib.Path:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    path.write_text(
        "\n".join(
            f"{key}={value}"
            for key, value in sorted(catalog["required_environment"].items())
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def generated_evidence(tmp_path: pathlib.Path) -> pathlib.Path:
    builder = load_module(BUILDER_SCRIPT, "build_billing_runtime_evidence")
    env_file = write_env(tmp_path / "billing-runtime.env")
    evidence = tmp_path / "billing-runtime-evidence.json"
    assert builder.main(["--catalog", str(CATALOG), "--env-file", str(env_file), "--output", str(evidence)]) == 0
    return evidence


def test_main_accepts_generated_billing_runtime_evidence(tmp_path: pathlib.Path) -> None:
    validator = load_module(VALIDATOR_SCRIPT, "validate_billing_runtime_evidence")
    evidence = generated_evidence(tmp_path)

    assert validator.main([str(evidence)]) == 0


def test_sale_ready_runtime_must_match_blocker_state(tmp_path: pathlib.Path) -> None:
    validator = load_module(VALIDATOR_SCRIPT, "validate_billing_runtime_evidence")
    evidence = generated_evidence(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["runtime_blockers"] = [
        {
            "type": "catalog_runtime_mismatch",
            "name": "BILLING_ALLOWED_PLANS",
            "reason": "forced mismatch",
        }
    ]
    evidence.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(AssertionError, match="sale_ready_runtime"):
        validator.validate_evidence(evidence)


def test_sensitive_entries_must_not_hash_actual_values(tmp_path: pathlib.Path) -> None:
    validator = load_module(VALIDATOR_SCRIPT, "validate_billing_runtime_evidence")
    evidence = generated_evidence(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    sensitive_entry = next(
        entry
        for entry in payload["required_environment"]
        if entry["name"] == "BILLING_WEBHOOK_SECRET"
    )
    sensitive_entry["actual_sha256"] = "ab" * 32
    evidence.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(AssertionError, match="sensitive actual values"):
        validator.validate_evidence(evidence)
