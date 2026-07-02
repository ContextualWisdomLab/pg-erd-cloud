from __future__ import annotations

import importlib.util
import json
import pathlib
from typing import Any

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "validate_billing_provider_catalog.py"


def load_validator() -> Any:
    assert SCRIPT.is_file(), "billing provider catalog validator script is missing"
    spec = importlib.util.spec_from_file_location("validate_billing_provider_catalog", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def valid_catalog() -> dict[str, Any]:
    return json.loads(
        (ROOT / "docs" / "operations" / "billing-provider-catalog.example.json")
        .read_text(encoding="utf-8")
    )


def write_catalog(path: pathlib.Path, payload: dict[str, Any]) -> pathlib.Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_main_validates_explicit_billing_catalog_path(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    catalog = write_catalog(tmp_path / "billing-provider-catalog.customer.json", valid_catalog())

    assert validator.main([str(catalog)]) == 0


def test_missing_explicit_billing_catalog_path_fails(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    missing = tmp_path / "missing-billing-provider-catalog.json"

    with pytest.raises(AssertionError, match="missing billing provider catalog"):
        validator.main([str(missing)])


def test_billing_catalog_rejects_raw_webhook_secret(tmp_path: pathlib.Path) -> None:
    validator = load_validator()
    payload = valid_catalog()
    payload["required_environment"]["BILLING_WEBHOOK_SECRET"] = "whsec_raw_secret"
    catalog = write_catalog(tmp_path / "billing-provider-catalog.customer.json", payload)

    with pytest.raises(AssertionError, match="BILLING_WEBHOOK_SECRET"):
        validator.validate_manifest(catalog)
