from __future__ import annotations

import importlib.util
import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "operations" / "build_commercial_evidence_index.py"
AUDIT_TESTS = ROOT / "scripts" / "ci" / "test_commercial_readiness_audit.py"


def load_index_builder() -> Any:
    assert SCRIPT.is_file(), "commercial evidence index script is missing"
    spec = importlib.util.spec_from_file_location("build_commercial_evidence_index", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_audit_test_helpers() -> Any:
    assert AUDIT_TESTS.is_file(), "commercial readiness audit tests are missing"
    spec = importlib.util.spec_from_file_location("commercial_readiness_audit_tests", AUDIT_TESTS)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def evidence_cli_args(paths: dict[str, list[pathlib.Path]]) -> list[str]:
    return [
        "--release-approval",
        str(paths["signed_release_approval"][0]),
        "--restore-drill",
        str(paths["customer_restore_drill"][0]),
        "--rollback-drill",
        str(paths["customer_rollback_drill"][0]),
        "--support-bundle",
        str(paths["support_bundle_evidence"][0]),
        "--billing-provider-catalog",
        str(paths["real_billing_provider_catalog"][0]),
        "--billing-runtime-evidence",
        str(paths["billing_runtime_evidence"][0]),
    ]


def test_index_builder_accepts_sale_ready_external_evidence(
    tmp_path: pathlib.Path,
) -> None:
    builder = load_index_builder()
    helpers = load_audit_test_helpers()
    paths = helpers.explicit_evidence_paths(tmp_path)
    output = tmp_path / "commercial-evidence-index.json"

    assert builder.main([*evidence_cli_args(paths), "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["index_schema_version"] == 1
    assert payload["sale_ready"] is True
    assert payload["decision"] == "ready_for_sale"
    assert payload["sale_blockers"] == []
    assert len(payload["evidence"]) == 6
    for entry in payload["evidence"]:
        assert entry["exists"] is True
        assert entry["gate_status"] == "ready"
        assert entry["explicit_validator_passed"] is True
        assert entry["explicit_sample_markers"] == []
        assert len(entry["sha256"]) == 64
        assert entry["size_bytes"] > 0
        assert "contents" not in entry


def test_index_builder_can_emit_incomplete_intake_blockers(
    tmp_path: pathlib.Path,
) -> None:
    builder = load_index_builder()
    output = tmp_path / "commercial-evidence-index.json"

    assert builder.main(["--allow-incomplete", "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["sale_ready"] is False
    assert payload["decision"] == "not_ready_for_sale"
    assert payload["evidence"] == []
    assert {blocker["id"] for blocker in payload["sale_blockers"]} == {
        "signed_release_approval",
        "customer_restore_drill",
        "customer_rollback_drill",
        "support_bundle_evidence",
        "real_billing_provider_catalog",
        "billing_runtime_evidence",
    }


def test_index_builder_fails_closed_when_incomplete_by_default(
    tmp_path: pathlib.Path,
) -> None:
    builder = load_index_builder()
    output = tmp_path / "commercial-evidence-index.json"

    assert builder.main(["--output", str(output)]) == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["sale_ready"] is False
    assert payload["sale_blockers"]
