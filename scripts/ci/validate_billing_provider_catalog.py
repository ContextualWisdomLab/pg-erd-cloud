#!/usr/bin/env python3
"""Validate billing provider catalog manifests for commercial releases."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys
from typing import Any
from urllib.parse import urlparse


ROOT = pathlib.Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "operations" / "billing-provider-catalog.example.json"

PLACEHOLDER_RE = re.compile(r"\b(tbd|todo|fixme|pending|placeholder)\b|[<>]", re.IGNORECASE)
PLAN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
EVENT_TYPE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

REQUIRED_TOP_LEVEL_STRINGS = (
    "catalog_version",
    "effective_date",
    "provider",
    "checkout_url",
    "portal_url",
    "support_url",
)

REQUIRED_ENVIRONMENT_KEYS = (
    "BILLING_ALLOWED_PLANS",
    "BILLING_CHECKOUT_URL",
    "BILLING_PORTAL_URL",
    "BILLING_SUPPORT_URL",
    "BILLING_WEBHOOK_SECRET",
    "BILLING_WEBHOOK_SIGNATURE_SECRET",
    "BILLING_ENTITLEMENT_EVENT_TYPES",
    "BILLING_CONTRACT_STATE_EVENTS_ENABLED",
)

SECRET_REF_PREFIXES = (
    "secret-manager:",
    "vault:",
    "aws-secretsmanager:",
    "gcp-secret-manager:",
    "azure-key-vault:",
)

BILLING_METHODS = {
    "subscription",
    "external_contract_invoice",
    "on_premises_license",
    "reseller_contract",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_text(value: Any, field: str) -> str:
    require(isinstance(value, str), f"{field} must be a string")
    text = value.strip()
    require(text, f"{field} must not be blank")
    require(PLACEHOLDER_RE.search(text) is None, f"{field} must not contain placeholders")
    return text


def require_https_url(value: Any, field: str) -> str:
    text = require_text(value, field)
    parsed = urlparse(text)
    require(parsed.scheme == "https", f"{field} must use https")
    require(bool(parsed.netloc), f"{field} must include a host")
    return text


def require_event_type(value: Any, field: str) -> str:
    text = require_text(value, field)
    require(EVENT_TYPE_RE.match(text) is not None, f"{field} has invalid event type")
    return text


def require_event_type_list(value: Any, field: str) -> list[str]:
    require(isinstance(value, list), f"{field} must be a list")
    require(len(value) > 0, f"{field} must not be empty")
    items = [require_event_type(item, f"{field}[{index}]") for index, item in enumerate(value)]
    require(len(items) == len(set(items)), f"{field} must not contain duplicates")
    return items


def csv_items(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def require_secret_reference(value: Any, field: str) -> str:
    text = require_text(value, field)
    require(
        text.startswith(SECRET_REF_PREFIXES),
        f"{field} must reference secret storage, not contain a raw secret",
    )
    return text


def load_manifest(path: pathlib.Path) -> dict[str, Any]:
    require(path.is_file(), f"missing billing provider catalog manifest: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path.relative_to(ROOT)} is invalid JSON: {exc}") from exc
    require(isinstance(payload, dict), f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def validate_plan(plan: Any, index: int) -> tuple[str, set[str], set[str], set[str]]:
    require(isinstance(plan, dict), f"allowed_plans[{index}] must be an object")
    plan_id = require_text(plan.get("plan_id"), f"allowed_plans[{index}].plan_id")
    require(PLAN_ID_RE.match(plan_id) is not None, f"allowed_plans[{index}].plan_id is invalid")
    require_text(plan.get("display_name"), f"allowed_plans[{index}].display_name")
    billing_method = require_text(plan.get("billing_method"), f"allowed_plans[{index}].billing_method")
    require(
        billing_method in BILLING_METHODS,
        f"allowed_plans[{index}].billing_method is unsupported",
    )
    currency = require_text(plan.get("contract_currency"), f"allowed_plans[{index}].contract_currency")
    require(CURRENCY_RE.match(currency) is not None, f"allowed_plans[{index}].contract_currency must be ISO 4217")
    require_text(plan.get("fulfillment_owner"), f"allowed_plans[{index}].fulfillment_owner")
    require_text(plan.get("support_sla"), f"allowed_plans[{index}].support_sla")
    require(
        isinstance(plan.get("seat_count_required"), bool),
        f"allowed_plans[{index}].seat_count_required must be a boolean",
    )
    entitlement_events = set(
        require_event_type_list(
            plan.get("entitlement_event_types"),
            f"allowed_plans[{index}].entitlement_event_types",
        )
    )
    active_events = set(
        require_event_type_list(
            plan.get("contract_state_active_event_types"),
            f"allowed_plans[{index}].contract_state_active_event_types",
        )
    )
    deactivated_events = set(
        require_event_type_list(
            plan.get("contract_state_deactivated_event_types"),
            f"allowed_plans[{index}].contract_state_deactivated_event_types",
        )
    )
    require(
        active_events.isdisjoint(deactivated_events),
        f"allowed_plans[{index}] active/deactivated event types must not overlap",
    )
    return plan_id, entitlement_events, active_events, deactivated_events


def validate_event_aliases(value: Any) -> None:
    require(isinstance(value, list), "event_type_aliases must be a list")
    seen_sources: set[str] = set()
    for index, alias in enumerate(value):
        require(isinstance(alias, dict), f"event_type_aliases[{index}] must be an object")
        source = require_event_type(alias.get("source"), f"event_type_aliases[{index}].source")
        target = require_event_type(alias.get("target"), f"event_type_aliases[{index}].target")
        require(source not in seen_sources, f"event_type_aliases[{index}].source duplicates {source}")
        require(source != target, f"event_type_aliases[{index}] source and target must differ")
        seen_sources.add(source)


def validate_manifest(path: pathlib.Path) -> None:
    payload = load_manifest(path)
    for field in REQUIRED_TOP_LEVEL_STRINGS:
        require_text(payload.get(field), field)
    try:
        dt.date.fromisoformat(str(payload["effective_date"]))
    except ValueError as exc:
        raise AssertionError("effective_date must use YYYY-MM-DD") from exc

    checkout_url = require_https_url(payload.get("checkout_url"), "checkout_url")
    portal_url = require_https_url(payload.get("portal_url"), "portal_url")
    support_url = require_https_url(payload.get("support_url"), "support_url")

    webhook_auth = payload.get("webhook_auth")
    require(isinstance(webhook_auth, dict), "webhook_auth must be an object")
    for field in ("shared_secret_env", "signature_secret_env"):
        env_name = require_text(webhook_auth.get(field), f"webhook_auth.{field}")
        require(ENV_NAME_RE.match(env_name) is not None, f"webhook_auth.{field} must be an env var name")

    allowed_plans = payload.get("allowed_plans")
    require(isinstance(allowed_plans, list), "allowed_plans must be a list")
    require(len(allowed_plans) > 0, "allowed_plans must not be empty")

    plan_ids: list[str] = []
    entitlement_events: set[str] = set()
    active_events: set[str] = set()
    deactivated_events: set[str] = set()
    for index, plan in enumerate(allowed_plans):
        plan_id, plan_entitlement, plan_active, plan_deactivated = validate_plan(plan, index)
        require(plan_id not in plan_ids, f"allowed_plans[{index}].plan_id duplicates {plan_id}")
        plan_ids.append(plan_id)
        entitlement_events.update(plan_entitlement)
        active_events.update(plan_active)
        deactivated_events.update(plan_deactivated)

    validate_event_aliases(payload.get("event_type_aliases"))

    required_environment = payload.get("required_environment")
    require(isinstance(required_environment, dict), "required_environment must be an object")
    for key in REQUIRED_ENVIRONMENT_KEYS:
        require_text(required_environment.get(key), f"required_environment.{key}")

    env_plan_ids = csv_items(str(required_environment["BILLING_ALLOWED_PLANS"]))
    require(set(env_plan_ids) == set(plan_ids), "BILLING_ALLOWED_PLANS must match allowed_plans plan_id values")
    require(required_environment["BILLING_CHECKOUT_URL"] == checkout_url, "BILLING_CHECKOUT_URL must match checkout_url")
    require(required_environment["BILLING_PORTAL_URL"] == portal_url, "BILLING_PORTAL_URL must match portal_url")
    require(required_environment["BILLING_SUPPORT_URL"] == support_url, "BILLING_SUPPORT_URL must match support_url")
    require_secret_reference(required_environment["BILLING_WEBHOOK_SECRET"], "required_environment.BILLING_WEBHOOK_SECRET")
    require_secret_reference(
        required_environment["BILLING_WEBHOOK_SIGNATURE_SECRET"],
        "required_environment.BILLING_WEBHOOK_SIGNATURE_SECRET",
    )

    env_entitlement_events = set(csv_items(str(required_environment["BILLING_ENTITLEMENT_EVENT_TYPES"])))
    require(
        entitlement_events.issubset(env_entitlement_events),
        "BILLING_ENTITLEMENT_EVENT_TYPES must include every plan entitlement event type",
    )
    require(
        str(required_environment["BILLING_CONTRACT_STATE_EVENTS_ENABLED"]).lower() == "true",
        "BILLING_CONTRACT_STATE_EVENTS_ENABLED must be true for commercial catalog manifests",
    )
    env_active_events = set(csv_items(str(required_environment.get("BILLING_CONTRACT_ACTIVE_EVENT_TYPES", ""))))
    env_deactivated_events = set(csv_items(str(required_environment.get("BILLING_CONTRACT_DEACTIVATED_EVENT_TYPES", ""))))
    require(active_events.issubset(env_active_events), "BILLING_CONTRACT_ACTIVE_EVENT_TYPES must include plan active events")
    require(
        deactivated_events.issubset(env_deactivated_events),
        "BILLING_CONTRACT_DEACTIVATED_EVENT_TYPES must include plan deactivated events",
    )


def main() -> int:
    validate_manifest(CATALOG_PATH)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validate_billing_provider_catalog.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
