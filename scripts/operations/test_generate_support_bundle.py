from __future__ import annotations

import importlib.util
import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "operations" / "generate_support_bundle.py"


def load_generator() -> Any:
    assert SCRIPT.is_file(), "support bundle generator script is missing"
    spec = importlib.util.spec_from_file_location("generate_support_bundle", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_support_bundle_redacts_sensitive_inputs(tmp_path: pathlib.Path) -> None:
    generator = load_generator()
    env_file = tmp_path / "deployment.env"
    env_file.write_text(
        "\n".join(
            [
                "LICENSE_MODE=required",
                "LICENSE_PUBLIC_KEY=public-key-material",
                "LICENSE_REVOKED_TOKEN_IDS=license-token-secret",
                "BILLING_ALLOWED_PLANS=enterprise",
                "BILLING_SUPPORT_URL=https://billing.example.com/support",
                "ACCOUNT_REACTIVATION_URL=https://billing.example.com/reactivate",
                "BILLING_WEBHOOK_SECRET=provider-secret",
                "BILLING_WEBHOOK_SIGNATURE_SECRET=signature-secret",
            ]
        ),
        encoding="utf-8",
    )
    healthz_file = tmp_path / "healthz.json"
    healthz_file.write_text(
        json.dumps({"ok": True, "database_dsn": "postgresql://user:dbpass@db/app"}),
        encoding="utf-8",
    )
    support_file = tmp_path / "support-account.json"
    support_file.write_text(
        json.dumps(
            {
                "subject": "customer-admin",
                "billing_support_url": "https://billing.example.com/support",
                "metadata": {"api_key": "sk_live_secret"},
                "recent_share_links": [
                    {
                        "name": "Board review",
                        "share_url": "https://app.example.com/share/share-token-secret",
                    }
                ],
                "recent_billing_events": [
                    {
                        "metadata_summary": [
                            {"key": "api_key", "value": "[redacted]"},
                            {"key": "seat_count", "value": "25"},
                        ]
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    alembic_file = tmp_path / "alembic-current.txt"
    alembic_file.write_text("0005_llm_draft_usage_event (head)\n", encoding="utf-8")
    log_file = tmp_path / "backend.log"
    log_file.write_text(
        "\n".join(
            [
                "failed DATABASE_URL=postgresql://user:dbpass@db/app",
                "Authorization: Bearer live-token-secret",
                "api_key=sk_live_secret private-key: top-secret",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "bundle.json"

    assert (
        generator.main(
            [
                "--commit-sha",
                "41f8b014f68813ba50fb9dca8dfdad280920fe2c",
                "--billing-provider-catalog-version",
                "catalog-2026-07-02",
                "--output",
                str(output),
                "--env-file",
                str(env_file),
                "--healthz-file",
                str(healthz_file),
                "--support-account-file",
                str(support_file),
                "--alembic-current-file",
                str(alembic_file),
                "--backend-log-file",
                str(log_file),
            ]
        )
        == 0
    )

    bundle = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(bundle, sort_keys=True)
    assert "41f8b014f68813ba50fb9dca8dfdad280920fe2c" in serialized
    assert bundle["license"]["mode"] == "required"
    assert bundle["license"]["verifier"] == "signed_token"
    assert bundle["deployment"]["compose_prod"]["sha256"]
    assert bundle["database"]["alembic_current"] == "0005_llm_draft_usage_event (head)"
    assert "seat_count" in serialized

    for leaked in (
        "dbpass",
        "live-token-secret",
        "sk_live_secret",
        "top-secret",
        "share-token-secret",
        "provider-secret",
        "signature-secret",
        "license-token-secret",
        "postgresql://user:dbpass",
    ):
        assert leaked not in serialized


def test_support_bundle_can_write_stdout(capsys: Any, tmp_path: pathlib.Path) -> None:
    generator = load_generator()

    assert (
        generator.main(
            [
                "--commit-sha",
                "41f8b014f68813ba50fb9dca8dfdad280920fe2c",
                "--billing-provider-catalog-version",
                "catalog-2026-07-02",
                "--output",
                "-",
                "--compose-prod-file",
                str(tmp_path / "missing-compose.yaml"),
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    bundle = json.loads(captured.out)
    assert bundle["deployment"]["compose_prod"]["exists"] is False
    assert bundle["deployment"]["compose_prod"]["sha256"] is None
