#!/usr/bin/env python3
"""Generate a redacted support bundle for commercial/on-premises handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Any, Iterable


ROOT = pathlib.Path(__file__).resolve().parents[2]

SECRET_KEY_FRAGMENTS = (
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
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b[\w.-]*(?:password|passwd|pwd|token|secret|private[_-]?key|"
    r"api[_-]?key|client[_-]?secret|authorization|dsn|card)[\w.-]*\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^,\s]+)"
)
CREDENTIAL_URL_RE = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]*://)([^/\s:@]+):([^@\s/]+)@"
)
QUERY_SECRET_RE = re.compile(
    r"(?i)([?&][\w.-]*(?:password|passwd|pwd|token|secret|private[_-]?key|"
    r"api[_-]?key|client[_-]?secret|authorization|dsn|card)[\w.-]*=)"
    r"([^&#\s]+)"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
REDACTED = "[redacted]"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_optional_text(path: pathlib.Path | None) -> str | None:
    if path is None:
        return None
    return _read_text(path)


def _sha256_file(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact_text(value: str) -> str:
    """Redact common secret assignments, bearer tokens, and URL credentials."""
    redacted = CREDENTIAL_URL_RE.sub(r"\1\2:" + REDACTED + "@", value)
    redacted = QUERY_SECRET_RE.sub(r"\1" + REDACTED, redacted)
    redacted = BEARER_RE.sub("Bearer " + REDACTED, redacted)
    return SECRET_ASSIGNMENT_RE.sub(r"\1" + REDACTED, redacted)


def _key_is_sensitive(key: str) -> bool:
    lowered = key.lower().replace(" ", "_")
    if lowered in SAFE_STRUCTURAL_KEYS:
        return False
    if lowered in RAW_METADATA_KEYS or lowered.endswith("_metadata"):
        return True
    if any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS):
        return True
    return any(fragment in lowered for fragment in PUBLIC_LINK_KEY_FRAGMENTS)


def redact_json(value: Any) -> Any:
    """Recursively redact JSON-like data without dropping structural context."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if _key_is_sensitive(key):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_json(raw_value)
        return redacted
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _load_json_or_text(path: pathlib.Path | None) -> Any | None:
    text = _read_optional_text(path)
    if text is None:
        return None
    try:
        return redact_json(json.loads(text))
    except json.JSONDecodeError:
        return redact_text(text.strip())


def _parse_env_file(path: pathlib.Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in _read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped.removeprefix("export ").strip()
        key, separator, value = stripped.partition("=")
        if separator != "=":
            continue
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _license_verifier(env: dict[str, str]) -> str:
    has_static_key = bool(env.get("LICENSE_KEY"))
    has_signed_token = bool(env.get("LICENSE_PUBLIC_KEY"))
    if has_static_key and has_signed_token:
        return "static_key_and_signed_token"
    if has_signed_token:
        return "signed_token"
    if has_static_key:
        return "static_key"
    return "none"


def _configured_names(env: dict[str, str], names: Iterable[str]) -> list[dict[str, Any]]:
    return [{"name": name, "configured": bool(env.get(name))} for name in names]


def _tail_redacted_lines(path: pathlib.Path | None, line_count: int) -> list[str]:
    text = _read_optional_text(path)
    if text is None:
        return []
    return [redact_text(line) for line in text.splitlines()[-line_count:]]


def generate_bundle(args: argparse.Namespace) -> dict[str, Any]:
    env = _parse_env_file(args.env_file)
    compose_path = args.compose_prod_file
    now = _utc_now()
    support_account = _load_json_or_text(args.support_account_file)
    healthz = _load_json_or_text(args.healthz_file)
    alembic_current = _read_optional_text(args.alembic_current_file)

    bundle: dict[str, Any] = {
        "bundle_schema_version": 1,
        "bundle_id": f"support-bundle-{now.replace(':', '').replace('-', '')}",
        "generated_at": now,
        "deployment": {
            "commit_sha": args.commit_sha,
            "billing_provider_catalog_version": args.billing_provider_catalog_version,
            "compose_prod": {
                "path": str(compose_path.relative_to(ROOT))
                if compose_path.is_relative_to(ROOT)
                else str(compose_path),
                "sha256": _sha256_file(compose_path),
                "exists": compose_path.is_file(),
            },
        },
        "database": {
            "alembic_current": redact_text(alembic_current.strip())
            if alembic_current
            else None,
        },
        "healthz": healthz,
        "license": {
            "mode": env.get("LICENSE_MODE", "unknown"),
            "verifier": _license_verifier(env),
            "revocation_environment_names": _configured_names(
                env,
                ("LICENSE_REVOKED_TOKEN_IDS", "LICENSE_REVOKED_SUBJECTS"),
            ),
        },
        "billing": {
            "provider_catalog_version": args.billing_provider_catalog_version,
            "environment_names": _configured_names(
                env,
                (
                    "BILLING_ALLOWED_PLANS",
                    "BILLING_CHECKOUT_URL",
                    "BILLING_PORTAL_URL",
                    "BILLING_SUPPORT_URL",
                    "ACCOUNT_REACTIVATION_URL",
                    "BILLING_ENTITLEMENT_EVENT_TYPES",
                    "BILLING_CONTRACT_STATE_EVENTS_ENABLED",
                ),
            ),
            "secret_environment_names": _configured_names(
                env,
                ("BILLING_WEBHOOK_SECRET", "BILLING_WEBHOOK_SIGNATURE_SECRET"),
            ),
        },
        "support_account_summary": support_account,
        "backend_error_log_tail": _tail_redacted_lines(
            args.backend_log_file,
            args.backend_log_lines,
        ),
        "redaction": {
            "applied": True,
            "rules": [
                "secret-like keys are replaced with [redacted]",
                "raw provider metadata fields are replaced with [redacted]",
                "public share URL/token fields are replaced with [redacted]",
                "URL credentials and secret query parameters are redacted in text",
                "bearer tokens and secret assignments are redacted in text",
            ],
        },
    }
    return redact_json(bundle)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a redacted pg-erd-cloud support bundle JSON file.",
    )
    parser.add_argument(
        "--commit-sha",
        required=True,
        help="Deployed application commit SHA.",
    )
    parser.add_argument(
        "--billing-provider-catalog-version",
        required=True,
        help="Version from the approved billing provider catalog manifest.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON path, or '-' for stdout.",
    )
    parser.add_argument(
        "--env-file",
        type=pathlib.Path,
        help="Optional deployment env file. Only safe config presence is emitted.",
    )
    parser.add_argument(
        "--compose-prod-file",
        type=pathlib.Path,
        default=ROOT / "compose.prod.yaml",
        help="Production compose file to fingerprint.",
    )
    parser.add_argument(
        "--alembic-current-file",
        type=pathlib.Path,
        help="File containing captured 'alembic current' output.",
    )
    parser.add_argument(
        "--healthz-file",
        type=pathlib.Path,
        help="File containing captured /healthz JSON or text output.",
    )
    parser.add_argument(
        "--support-account-file",
        type=pathlib.Path,
        help="File containing GET /api/billing/support/account JSON output.",
    )
    parser.add_argument(
        "--backend-log-file",
        type=pathlib.Path,
        help="File containing recent backend error logs.",
    )
    parser.add_argument(
        "--backend-log-lines",
        type=int,
        default=80,
        help="Number of backend log lines to include after redaction.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.backend_log_lines < 1:
        parser.error("--backend-log-lines must be greater than 0")

    bundle = generate_bundle(args)
    payload = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output == "-":
        print(payload)
    else:
        output_path = pathlib.Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
