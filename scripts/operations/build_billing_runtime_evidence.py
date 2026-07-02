#!/usr/bin/env python3
"""Build redacted billing runtime evidence from a provider catalog and env file."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "docs" / "operations" / "billing-provider-catalog.example.json"

SECRET_REF_PREFIXES = (
    "secret-manager:",
    "vault:",
    "aws-secretsmanager:",
    "gcp-secret-manager:",
    "azure-key-vault:",
)
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
ENV_ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=(.*)$")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _relative(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _resolve(path: pathlib.Path) -> pathlib.Path:
    return path if path.is_absolute() else ROOT / path


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{_relative(path)} must contain a JSON object")
    return payload


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_env_file(path: pathlib.Path) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    duplicates: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ENV_ASSIGNMENT_RE.match(line)
        if not match:
            continue
        key = match.group(1)
        if key in values and key not in duplicates:
            duplicates.append(key)
        values[key] = _strip_quotes(match.group(2))
    return values, sorted(duplicates)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace(" ", "_")
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _is_secret_reference(value: str) -> bool:
    return value.startswith(SECRET_REF_PREFIXES)


def _entry(name: str, expected: str, actual: str | None) -> dict[str, Any]:
    sensitive = _is_sensitive_key(name)
    configured = bool(actual)
    entry: dict[str, Any] = {
        "name": name,
        "sensitive": sensitive,
        "configured": configured,
        "value_redacted": True,
        "expected_sha256": _sha256_text(expected),
    }
    if sensitive:
        secret_reference_configured = configured and _is_secret_reference(str(actual))
        raw_secret_material_observed = configured and not secret_reference_configured
        entry.update(
            {
                "secret_reference_configured": secret_reference_configured,
                "raw_secret_material_observed": raw_secret_material_observed,
                "matches_catalog": secret_reference_configured
                and _sha256_text(str(actual)) == entry["expected_sha256"],
            }
        )
        if secret_reference_configured:
            entry["actual_reference_sha256"] = _sha256_text(str(actual))
        return entry

    entry.update(
        {
            "matches_catalog": configured and str(actual) == expected,
        }
    )
    if configured:
        entry["actual_sha256"] = _sha256_text(str(actual))
    return entry


def _runtime_blockers(
    entries: list[dict[str, Any]],
    duplicate_keys: list[str],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for key in duplicate_keys:
        blockers.append(
            {
                "type": "duplicate_environment_key",
                "name": key,
                "reason": "Deployment env file defines the required key more than once.",
            }
        )
    for entry in entries:
        name = str(entry["name"])
        if not entry["configured"]:
            blockers.append(
                {
                    "type": "missing_required_environment",
                    "name": name,
                    "reason": "Required billing runtime environment key is not configured.",
                }
            )
            continue
        if entry["sensitive"] and entry.get("raw_secret_material_observed") is True:
            blockers.append(
                {
                    "type": "raw_secret_material_in_environment_file",
                    "name": name,
                    "reason": "Use a secret storage reference in the reviewed env file, not raw secret material.",
                }
            )
            continue
        if entry["matches_catalog"] is not True:
            blockers.append(
                {
                    "type": "catalog_runtime_mismatch",
                    "name": name,
                    "reason": "Runtime environment value does not match the approved billing provider catalog.",
                }
            )
    return blockers


def build_evidence(catalog_path: pathlib.Path, env_file: pathlib.Path) -> dict[str, Any]:
    catalog_path = _resolve(catalog_path)
    env_file = _resolve(env_file)
    catalog = _load_json(catalog_path)
    env_values, duplicate_keys = parse_env_file(env_file)
    required_environment = catalog.get("required_environment")
    if not isinstance(required_environment, dict) or not required_environment:
        raise ValueError("billing provider catalog must define required_environment")

    entries = [
        _entry(str(name), str(expected), env_values.get(str(name)))
        for name, expected in sorted(required_environment.items())
    ]
    duplicate_required_keys = [
        key for key in duplicate_keys if key in required_environment
    ]
    blockers = _runtime_blockers(entries, duplicate_required_keys)
    configured_count = sum(1 for entry in entries if entry["configured"])
    non_secret_entries = [entry for entry in entries if not entry["sensitive"]]
    secret_entries = [entry for entry in entries if entry["sensitive"]]
    summary = {
        "required_count": len(entries),
        "configured_required_count": configured_count,
        "all_required_environment_configured": configured_count == len(entries),
        "all_non_secret_values_match_catalog": all(
            entry["matches_catalog"] is True for entry in non_secret_entries
        ),
        "all_secret_references_match_catalog": all(
            entry["matches_catalog"] is True for entry in secret_entries
        ),
        "raw_secret_material_observed": any(
            entry.get("raw_secret_material_observed") is True for entry in secret_entries
        ),
    }
    summary["sale_ready_runtime"] = not blockers

    return {
        "evidence_schema_version": 1,
        "generated_at": _utc_now(),
        "catalog": {
            "path": _relative(catalog_path),
            "sha256": _sha256_file(catalog_path),
            "catalog_version": catalog.get("catalog_version"),
            "provider": catalog.get("provider"),
            "effective_date": catalog.get("effective_date"),
        },
        "runtime_environment": {
            "source": "env_file",
            "path": _relative(env_file),
            "sha256": _sha256_file(env_file),
            "duplicate_required_keys": duplicate_required_keys,
        },
        "required_environment": entries,
        "summary": summary,
        "runtime_blockers": blockers,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create redacted evidence proving a deployment env file matches the "
            "approved billing provider catalog without emitting raw values."
        )
    )
    parser.add_argument(
        "--catalog",
        type=pathlib.Path,
        default=DEFAULT_CATALOG,
        help="Billing provider catalog JSON path.",
    )
    parser.add_argument(
        "--env-file",
        type=pathlib.Path,
        required=True,
        help="Deployment env file to compare with catalog required_environment.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output JSON path. Use '-' for stdout. Default: '-'.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Return exit code 0 even when runtime evidence has blockers.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence = build_evidence(args.catalog, args.env_file)
    payload = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output == "-":
        print(payload)
    else:
        output_path = pathlib.Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    if evidence["runtime_blockers"] and not args.allow_incomplete:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
