from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.license_gate import require_active_license
from app.license_tokens import generate_license_key_pair, issue_license_token
from app.settings import settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_issued_license_token_is_accepted_by_license_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_pair = generate_license_key_pair()
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", key_pair.public_key)
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    token = issue_license_token(
        private_key=key_pair.private_key,
        subject="customer-acme",
        plan="enterprise",
        token_id="license-2026-07",
        expires_at=int(time.time()) + 3600,
        seats=25,
    )

    require_active_license(x_license_key=token)


def test_issued_license_token_can_be_revoked_by_token_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_pair = generate_license_key_pair()
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", key_pair.public_key)
    monkeypatch.setattr(settings, "license_revoked_token_ids", "license-2026-07")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    token = issue_license_token(
        private_key=key_pair.private_key,
        subject="customer-acme",
        plan="enterprise",
        token_id="license-2026-07",
        expires_at=int(time.time()) + 3600,
    )

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key=token)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "license token is revoked"


def test_license_token_cli_issues_verifiable_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_pair = generate_license_key_pair()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.license_tokens",
            "issue",
            "--private-key",
            key_pair.private_key,
            "--sub",
            "customer-acme",
            "--plan",
            "enterprise",
            "--jti",
            "license-2026-07",
            "--exp",
            str(int(time.time()) + 3600),
            "--seats",
            "25",
        ],
        cwd=BACKEND_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", key_pair.public_key)
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    require_active_license(x_license_key=completed.stdout.strip())


def test_license_keypair_cli_outputs_public_verifier() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.license_tokens",
            "generate-keypair",
            "--format",
            "json",
        ],
        cwd=BACKEND_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)

    assert sorted(payload) == ["private_key", "public_key"]
    assert payload["private_key"]
    assert payload["public_key"]
