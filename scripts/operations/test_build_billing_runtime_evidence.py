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


def load_builder() -> Any:
    assert BUILDER_SCRIPT.is_file(), "billing runtime evidence builder is missing"
    spec = importlib.util.spec_from_file_location("build_billing_runtime_evidence", BUILDER_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_validator() -> Any:
    assert VALIDATOR_SCRIPT.is_file(), "billing runtime evidence validator is missing"
    spec = importlib.util.spec_from_file_location("validate_billing_runtime_evidence", VALIDATOR_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_env(path: pathlib.Path, overrides: dict[str, str] | None = None) -> pathlib.Path:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    values = dict(catalog["required_environment"])
    values.update(overrides or {})
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(values.items())) + "\n",
        encoding="utf-8",
    )
    return path


def test_builder_emits_sale_ready_runtime_evidence_without_values(
    tmp_path: pathlib.Path,
) -> None:
    builder = load_builder()
    validator = load_validator()
    env_file = write_env(tmp_path / "billing-runtime.env")
    output = tmp_path / "billing-runtime-evidence.json"

    assert builder.main(["--catalog", str(CATALOG), "--env-file", str(env_file), "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["evidence_schema_version"] == 1
    assert payload["summary"]["sale_ready_runtime"] is True
    assert payload["runtime_blockers"] == []
    assert payload["catalog"]["sha256"]
    serialized = json.dumps(payload, sort_keys=True)
    assert "https://billing.example.com/checkout" not in serialized
    assert "secret-manager:pg-erd-cloud/billing-webhook-secret" not in serialized
    assert "actual_value" not in serialized
    validator.validate_evidence(output)


def test_builder_fails_closed_on_catalog_runtime_mismatch(
    tmp_path: pathlib.Path,
) -> None:
    builder = load_builder()
    env_file = write_env(
        tmp_path / "billing-runtime.env",
        {"BILLING_ALLOWED_PLANS": "enterprise"},
    )
    output = tmp_path / "billing-runtime-evidence.json"

    assert builder.main(["--catalog", str(CATALOG), "--env-file", str(env_file), "--output", str(output)]) == 1

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["sale_ready_runtime"] is False
    assert {
        (blocker["type"], blocker["name"])
        for blocker in payload["runtime_blockers"]
    } == {("catalog_runtime_mismatch", "BILLING_ALLOWED_PLANS")}


def test_builder_redacts_and_rejects_raw_secret_material(
    tmp_path: pathlib.Path,
) -> None:
    builder = load_builder()
    env_file = write_env(
        tmp_path / "billing-runtime.env",
        {"BILLING_WEBHOOK_SECRET": "whsec_live_secret_material"},
    )
    output = tmp_path / "billing-runtime-evidence.json"

    assert builder.main(["--catalog", str(CATALOG), "--env-file", str(env_file), "--output", str(output)]) == 1

    payload = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, sort_keys=True)
    assert "whsec_live_secret_material" not in serialized
    assert "raw_secret_material_in_environment_file" in serialized
    load_validator().validate_evidence(output)


def test_builder_reports_duplicate_required_environment_keys(
    tmp_path: pathlib.Path,
) -> None:
    builder = load_builder()
    env_file = write_env(tmp_path / "billing-runtime.env")
    with env_file.open("a", encoding="utf-8") as handle:
        handle.write("UNRELATED_KEY=first\nUNRELATED_KEY=second\n")
        handle.write("BILLING_ALLOWED_PLANS=enterprise,onprem-enterprise\n")
    output = tmp_path / "billing-runtime-evidence.json"

    assert builder.main(["--catalog", str(CATALOG), "--env-file", str(env_file), "--output", str(output)]) == 1

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["runtime_environment"]["duplicate_required_keys"] == [
        "BILLING_ALLOWED_PLANS"
    ]
    assert {
        (blocker["type"], blocker["name"])
        for blocker in payload["runtime_blockers"]
    } == {("duplicate_environment_key", "BILLING_ALLOWED_PLANS")}


def test_validator_rejects_raw_value_fields(tmp_path: pathlib.Path) -> None:
    builder = load_builder()
    validator = load_validator()
    env_file = write_env(tmp_path / "billing-runtime.env")
    output = tmp_path / "billing-runtime-evidence.json"
    assert builder.main(["--catalog", str(CATALOG), "--env-file", str(env_file), "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["required_environment"][0]["actual_value"] = "https://billing.example.com/checkout"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(AssertionError, match="raw values"):
        validator.validate_evidence(output)
