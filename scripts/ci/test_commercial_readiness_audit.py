from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
from typing import Any

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "commercial_readiness_audit.py"
RUNTIME_BUILDER_SCRIPT = ROOT / "scripts" / "operations" / "build_billing_runtime_evidence.py"


def load_audit() -> Any:
    assert SCRIPT.is_file(), "commercial readiness audit script is missing"
    spec = importlib.util.spec_from_file_location("commercial_readiness_audit", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_runtime_builder() -> Any:
    assert RUNTIME_BUILDER_SCRIPT.is_file(), "billing runtime evidence builder is missing"
    spec = importlib.util.spec_from_file_location(
        "build_billing_runtime_evidence",
        RUNTIME_BUILDER_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_report_flags_example_only_evidence() -> None:
    audit = load_audit()

    report = audit.generate_report()

    assert report["schema_ready"] is True
    assert report["real_evidence_ready"] is False
    assert report["sale_ready"] is False
    no_go_ids = {
        gate["id"]
        for gate in report["real_evidence_gates"]
        if gate["status"] == "no_go"
    }
    assert "signed_release_approval" in no_go_ids
    assert "customer_rollback_drill" in no_go_ids
    assert "real_billing_provider_catalog" in no_go_ids
    assert "billing_runtime_evidence" in no_go_ids
    assert {blocker["id"] for blocker in report["sale_blockers"]} == no_go_ids
    assert all(blocker["type"] == "real_evidence" for blocker in report["sale_blockers"])
    assert all(blocker["reason"] for blocker in report["sale_blockers"])
    assert report["review_queue_is_blocker"] is False
    assert report["queued_checks_are_blocker"] is False


def test_strict_mode_fails_when_not_sale_ready() -> None:
    audit = load_audit()

    assert audit.main(["--strict"]) == 1


def test_report_can_write_json(tmp_path: pathlib.Path) -> None:
    audit = load_audit()
    output = tmp_path / "commercial-readiness-audit.json"

    assert audit.main(["--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"] == "not_ready_for_sale"
    assert payload["schema_ready"] is True
    assert payload["sale_blockers"]


def copy_example(path: pathlib.Path, target_dir: pathlib.Path, name: str) -> pathlib.Path:
    target = target_dir / name
    shutil.copyfile(path, target)
    return target


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> pathlib.Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def renamed_example_evidence_paths(tmp_path: pathlib.Path) -> dict[str, list[pathlib.Path]]:
    runtime_builder = load_runtime_builder()
    runtime_evidence = runtime_builder.build_evidence(
        ROOT / "docs" / "operations" / "billing-provider-catalog.example.json",
        ROOT / "docs" / "operations" / "billing-runtime.env.example",
    )
    return {
        "signed_release_approval": [
            copy_example(
                ROOT / "docs" / "legal" / "release-approvals" / "release-approval.example.json",
                tmp_path,
                "release-approval.customer.json",
            )
        ],
        "customer_restore_drill": [
            copy_example(
                ROOT / "docs" / "operations" / "restore-drills" / "restore-drill.example.json",
                tmp_path,
                "restore-drill.customer.json",
            )
        ],
        "customer_rollback_drill": [
            copy_example(
                ROOT / "docs" / "operations" / "rollback-drills" / "rollback-drill.example.json",
                tmp_path,
                "rollback-drill.customer.json",
            )
        ],
        "support_bundle_evidence": [
            copy_example(
                ROOT / "docs" / "operations" / "support-bundles" / "support-bundle.example.json",
                tmp_path,
                "support-bundle.customer.json",
            )
        ],
        "real_billing_provider_catalog": [
            copy_example(
                ROOT / "docs" / "operations" / "billing-provider-catalog.example.json",
                tmp_path,
                "billing-provider-catalog.customer.json",
            )
        ],
        "billing_runtime_evidence": [
            write_json(
                tmp_path / "billing-runtime-evidence.customer.json",
                runtime_evidence,
            )
        ],
    }


def explicit_evidence_paths(tmp_path: pathlib.Path) -> dict[str, list[pathlib.Path]]:
    release = load_json(ROOT / "docs" / "legal" / "release-approvals" / "release-approval.example.json")
    release.update(
        {
            "commit_sha": "2b20d9894b4693dad7d12e98e2e0fb9aea6eae32",
            "product_owner": "Product Owner product@acme-corp.internal",
            "legal_approver": "Legal Approver legal@acme-corp.internal",
            "security_approver": "Security Approver security@acme-corp.internal",
            "support_approver": "Support Approver support@acme-corp.internal",
            "support_channel": "contract-support@acme-corp.internal",
            "vulnerability_owner": "security@acme-corp.internal",
        }
    )

    restore = load_json(ROOT / "docs" / "operations" / "restore-drills" / "restore-drill.example.json")
    restore["app_secret_source"] = "vault://customer-production/pg-erd-cloud/app-secret"
    restore["backup_artifact"]["sha256"] = "ab" * 32

    rollback = load_json(ROOT / "docs" / "operations" / "rollback-drills" / "rollback-drill.example.json")
    rollback["environment"] = "production-staging"
    rollback["backup_artifact"]["path"] = "backups/pg-erd-cloud-20260702T000000Z.dump"
    rollback["backup_artifact"]["sha256"] = "ef" * 32
    rollback["dry_run"]["sql_sha256"] = "12" * 32

    support = load_json(ROOT / "docs" / "operations" / "support-bundles" / "support-bundle.example.json")
    support["deployment"]["commit_sha"] = "2b20d9894b4693dad7d12e98e2e0fb9aea6eae32"
    support["deployment"]["compose_prod"]["sha256"] = "cd" * 32
    support["support_account_summary"]["billing_support_url"] = "https://support.acme-corp.internal/pg-erd-cloud"

    billing = load_json(ROOT / "docs" / "operations" / "billing-provider-catalog.example.json")
    billing["checkout_url"] = "https://billing.acme-corp.internal/checkout"
    billing["portal_url"] = "https://billing.acme-corp.internal/portal"
    billing["support_url"] = "https://support.acme-corp.internal/billing"
    billing["allowed_plans"][0]["fulfillment_owner"] = "Billing Ops billing@acme-corp.internal"
    billing["allowed_plans"][1]["fulfillment_owner"] = "Contract Ops contracts@acme-corp.internal"
    billing["required_environment"]["BILLING_CHECKOUT_URL"] = billing["checkout_url"]
    billing["required_environment"]["BILLING_PORTAL_URL"] = billing["portal_url"]
    billing["required_environment"]["BILLING_SUPPORT_URL"] = billing["support_url"]
    billing_path = write_json(tmp_path / "billing-provider-catalog.customer.json", billing)
    runtime_env_path = tmp_path / "billing-runtime.customer.env"
    runtime_env_path.write_text(
        "\n".join(
            f"{key}={value}"
            for key, value in sorted(billing["required_environment"].items())
        )
        + "\n",
        encoding="utf-8",
    )
    runtime_builder = load_runtime_builder()
    runtime_evidence = runtime_builder.build_evidence(billing_path, runtime_env_path)

    return {
        "signed_release_approval": [
            write_json(tmp_path / "release-approval.customer.json", release)
        ],
        "customer_restore_drill": [
            write_json(tmp_path / "restore-drill.customer.json", restore)
        ],
        "customer_rollback_drill": [
            write_json(tmp_path / "rollback-drill.customer.json", rollback)
        ],
        "support_bundle_evidence": [
            write_json(tmp_path / "support-bundle.customer.json", support)
        ],
        "real_billing_provider_catalog": [billing_path],
        "billing_runtime_evidence": [
            write_json(
                tmp_path / "billing-runtime-evidence.customer.json",
                runtime_evidence,
            )
        ],
    }


def test_report_rejects_renamed_example_evidence_paths(tmp_path: pathlib.Path) -> None:
    audit = load_audit()

    report = audit.generate_report(renamed_example_evidence_paths(tmp_path))

    assert report["schema_ready"] is True
    assert report["real_evidence_ready"] is False
    assert report["sale_ready"] is False
    gates_with_sample_markers = [
        gate
        for gate in report["real_evidence_gates"]
        if gate["explicit_sample_markers"]
    ]
    assert {gate["id"] for gate in gates_with_sample_markers} == {
        "signed_release_approval",
        "customer_restore_drill",
        "customer_rollback_drill",
        "support_bundle_evidence",
        "real_billing_provider_catalog",
        "billing_runtime_evidence",
    }


def test_report_accepts_explicit_real_evidence_paths(tmp_path: pathlib.Path) -> None:
    audit = load_audit()

    report = audit.generate_report(explicit_evidence_paths(tmp_path))

    assert report["schema_ready"] is True
    assert report["real_evidence_ready"] is True
    assert report["sale_ready"] is True
    assert report["decision"] == "ready_for_sale"
    assert report["sale_blockers"] == []
    for gate in report["real_evidence_gates"]:
        assert gate["status"] == "ready"
        assert gate["explicit_validator_passed"] is True
        assert gate["explicit_evidence_files"]


def test_strict_mode_accepts_explicit_real_evidence_paths(tmp_path: pathlib.Path) -> None:
    audit = load_audit()
    paths = explicit_evidence_paths(tmp_path)

    assert audit.main(
        [
            "--strict",
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
    ) == 0


def support_bundle_rule(directory: pathlib.Path) -> dict[str, Any]:
    return {
        "id": "support_bundle_evidence",
        "label": "Redacted customer support bundle evidence",
        "required_for": "paid_pilot_support",
        "directory": str(directory),
        "pattern": "*.json",
        "example_names": {"support-bundle.example.json"},
        "no_go_reason": "Only the example support bundle manifest is present.",
    }


def test_repo_real_evidence_rejects_sample_markers(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = load_audit()
    evidence_dir = tmp_path / "support-bundles"
    evidence_dir.mkdir()
    sample = load_json(ROOT / "docs" / "operations" / "support-bundles" / "support-bundle.example.json")
    write_json(evidence_dir / "support-bundle.customer.json", sample)
    monkeypatch.setattr(audit, "REAL_EVIDENCE_RULES", (support_bundle_rule(evidence_dir),))

    report = audit.generate_report()

    gate = report["real_evidence_gates"][0]
    assert report["real_evidence_ready"] is False
    assert gate["status"] == "no_go"
    assert gate["repo_validator_passed"] is True
    assert gate["repo_sample_markers"]
    assert gate["no_go_reason"] == "Repository evidence files still contain example or synthetic evidence markers."
    assert report["sale_blockers"] == [
        {
            "type": "real_evidence",
            "id": "support_bundle_evidence",
            "label": "Redacted customer support bundle evidence",
            "required_for": "paid_pilot_support",
            "reason": "Repository evidence files still contain example or synthetic evidence markers.",
            "repo_real_evidence_files": [str(evidence_dir / "support-bundle.customer.json")],
            "repo_sample_markers": gate["repo_sample_markers"],
            "explicit_evidence_files": [],
            "explicit_sample_markers": [],
        }
    ]


def test_repo_real_evidence_accepts_sanitized_manifest(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = load_audit()
    evidence_dir = tmp_path / "support-bundles"
    evidence_dir.mkdir()
    payload = load_json(ROOT / "docs" / "operations" / "support-bundles" / "support-bundle.example.json")
    payload["deployment"]["commit_sha"] = "8f92cb06e9d6145f6aa1a047c2ef98ea2dc0b613"
    payload["deployment"]["compose_prod"]["sha256"] = "cd" * 32
    payload["support_account_summary"]["billing_support_url"] = "https://support.acme-corp.internal/pg-erd-cloud"
    write_json(evidence_dir / "support-bundle.customer.json", payload)
    monkeypatch.setattr(audit, "REAL_EVIDENCE_RULES", (support_bundle_rule(evidence_dir),))

    report = audit.generate_report()

    gate = report["real_evidence_gates"][0]
    assert report["real_evidence_ready"] is True
    assert gate["status"] == "ready"
    assert gate["repo_validator_passed"] is True
    assert gate["repo_sample_markers"] == []
    assert report["sale_blockers"] == []
