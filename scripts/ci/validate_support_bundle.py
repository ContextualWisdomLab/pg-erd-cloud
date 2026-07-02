#!/usr/bin/env python3
"""Validate redacted support bundle evidence manifests."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUNDLE_DIR = ROOT / "docs" / "operations" / "support-bundles"
EXAMPLE_NAME = "support-bundle.example.json"

SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
CREDENTIAL_URL_RE = re.compile(
    r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:(?!\[redacted\])[^@\s/]+@"
)
QUERY_SECRET_RE = re.compile(
    r"(?i)[?&][\w.-]*(?:password|passwd|pwd|token|secret|private[_-]?key|"
    r"api[_-]?key|client[_-]?secret|authorization|dsn|card)[\w.-]*="
    r"(?!\[redacted\])[^&#\s]+"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b[\w.-]*(?:password|passwd|pwd|token|secret|private[_-]?key|"
    r"api[_-]?key|client[_-]?secret|authorization|dsn|card)[\w.-]*\s*[:=]\s*"
    r"(?!\[redacted\])(\"[^\"]*\"|'[^']*'|[^,\s]+)"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+(?!\[redacted\])[A-Za-z0-9._~+/=-]+")
SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "client_secret",
    "private-key",
    "private_key",
    "password",
    "passwd",
    "api-key",
    "api_key",
    "secret",
    "token",
    "pwd",
    "dsn",
    "card",
)
RAW_METADATA_KEYS = {
    "metadata",
    "metadata_json",
    "raw_metadata",
    "provider_metadata",
    "billing_metadata",
}
PUBLIC_LINK_KEY_FRAGMENTS = (
    "public_url",
    "share_url",
    "share_token",
    "link_token",
    "url_token",
)
SAFE_STRUCTURAL_KEYS = {
    "environment_names",
    "secret_environment_names",
    "revocation_environment_names",
    "rules",
}
FORBIDDEN_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "sk_live_",
    "whsec_",
    "xoxb-",
    "AKIA",
)
LICENSE_MODES = {"off", "required", "unknown"}
LICENSE_VERIFIERS = {
    "none",
    "static_key",
    "signed_token",
    "static_key_and_signed_token",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_text(value: Any, field: str) -> str:
    require(isinstance(value, str), f"{field} must be a string")
    text = value.strip()
    require(text, f"{field} must not be blank")
    return text


def require_mapping(value: Any, field: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{field} must be an object")
    return value


def require_bool(value: Any, field: str) -> bool:
    require(isinstance(value, bool), f"{field} must be a boolean")
    return value


def require_env_presence_list(value: Any, field: str) -> None:
    require(isinstance(value, list), f"{field} must be a list")
    require(value, f"{field} must not be empty")
    for index, item in enumerate(value):
        entry = require_mapping(item, f"{field}[{index}]")
        name = require_text(entry.get("name"), f"{field}[{index}].name")
        require(ENV_NAME_RE.match(name) is not None, f"{field}[{index}].name is invalid")
        require_bool(entry.get("configured"), f"{field}[{index}].configured")


def display_path(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace(" ", "_")
    if lowered in SAFE_STRUCTURAL_KEYS:
        return False
    if lowered in RAW_METADATA_KEYS or lowered.endswith("_metadata"):
        return True
    if any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS):
        return True
    return any(fragment in lowered for fragment in PUBLIC_LINK_KEY_FRAGMENTS)


def _scan_redaction(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}" if path else key
            if key.lower().replace(" ", "_") == "rules":
                continue
            if _is_sensitive_key(key):
                require(raw_value == "[redacted]", f"{child_path} must be [redacted]")
            else:
                _scan_redaction(raw_value, child_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_redaction(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        require(CREDENTIAL_URL_RE.search(value) is None, f"{path} contains URL credentials")
        require(QUERY_SECRET_RE.search(value) is None, f"{path} contains a secret query value")
        require(SECRET_ASSIGNMENT_RE.search(value) is None, f"{path} contains a secret assignment")
        require(BEARER_RE.search(value) is None, f"{path} contains a bearer token")
        for marker in FORBIDDEN_MARKERS:
            require(marker not in value, f"{path} contains forbidden marker {marker}")


def validate_bundle(path: pathlib.Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{display_path(path)} is invalid JSON: {exc}") from exc
    require_mapping(payload, display_path(path))

    require(payload.get("bundle_schema_version") == 1, "bundle_schema_version must be 1")
    require_text(payload.get("bundle_id"), "bundle_id")
    generated_at = require_text(payload.get("generated_at"), "generated_at")
    try:
        dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssertionError("generated_at must be ISO-8601") from exc

    deployment = require_mapping(payload.get("deployment"), "deployment")
    commit_sha = require_text(deployment.get("commit_sha"), "deployment.commit_sha")
    require(SHA_RE.match(commit_sha) is not None, "deployment.commit_sha must be 7-40 lowercase hex")
    require_text(
        deployment.get("billing_provider_catalog_version"),
        "deployment.billing_provider_catalog_version",
    )
    compose_prod = require_mapping(deployment.get("compose_prod"), "deployment.compose_prod")
    compose_exists = require_bool(compose_prod.get("exists"), "deployment.compose_prod.exists")
    require_text(compose_prod.get("path"), "deployment.compose_prod.path")
    compose_sha = compose_prod.get("sha256")
    if compose_exists:
        require(
            isinstance(compose_sha, str) and SHA256_RE.match(compose_sha) is not None,
            "deployment.compose_prod.sha256 must be a 64-character hex digest when exists=true",
        )

    database = require_mapping(payload.get("database"), "database")
    require_text(database.get("alembic_current"), "database.alembic_current")

    license_payload = require_mapping(payload.get("license"), "license")
    license_mode = require_text(license_payload.get("mode"), "license.mode")
    require(license_mode in LICENSE_MODES, "license.mode is unsupported")
    verifier = require_text(license_payload.get("verifier"), "license.verifier")
    require(verifier in LICENSE_VERIFIERS, "license.verifier is unsupported")
    require_env_presence_list(
        license_payload.get("revocation_environment_names"),
        "license.revocation_environment_names",
    )

    billing = require_mapping(payload.get("billing"), "billing")
    require_text(billing.get("provider_catalog_version"), "billing.provider_catalog_version")
    require_env_presence_list(billing.get("environment_names"), "billing.environment_names")
    require_env_presence_list(
        billing.get("secret_environment_names"),
        "billing.secret_environment_names",
    )

    require(payload.get("healthz") is not None, "healthz is required")
    require_mapping(payload.get("support_account_summary"), "support_account_summary")
    backend_log = payload.get("backend_error_log_tail")
    require(isinstance(backend_log, list), "backend_error_log_tail must be a list")
    for index, line in enumerate(backend_log):
        require_text(line, f"backend_error_log_tail[{index}]")

    redaction = require_mapping(payload.get("redaction"), "redaction")
    require(redaction.get("applied") is True, "redaction.applied must be true")
    rules = redaction.get("rules")
    require(isinstance(rules, list) and rules, "redaction.rules must be a non-empty list")

    _scan_redaction(payload, "")


def main() -> int:
    require(BUNDLE_DIR.is_dir(), "support bundle manifest directory is missing")
    bundles = sorted(BUNDLE_DIR.glob("*.json"))
    require(bundles, "at least the example support bundle manifest is required")

    example = BUNDLE_DIR / EXAMPLE_NAME
    require(example in bundles, f"{EXAMPLE_NAME} is required")
    for bundle in bundles:
        validate_bundle(bundle)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validate_support_bundle.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
