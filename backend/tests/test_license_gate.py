from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.license_gate import require_active_license
from app.settings import settings


def test_license_gate_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "license_mode", "off")
    monkeypatch.setattr(settings, "license_key", "x" * 64)

    require_active_license(x_license_key=None)


def test_license_gate_rejects_missing_license_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", "x" * 32)

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key=None)

    assert exc_info.value.status_code == 403


def test_license_gate_rejects_wrong_license_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", "x" * 32)

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key="wrong-key")

    assert exc_info.value.status_code == 403


def test_license_gate_rejects_when_mode_is_required_but_key_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key="anything")

    assert exc_info.value.status_code == 500


def test_license_gate_accepts_valid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", "x" * 32)

    require_active_license(x_license_key="x" * 32)
