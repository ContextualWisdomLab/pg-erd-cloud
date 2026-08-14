"""Execution-neutral pre-apply revalidation manifest contract tests."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.forward.migration_plan import COMPILER_VERSION
from app.forward.pre_apply_revalidation import (
    PreApplyRevalidationContractError,
    compile_pre_apply_revalidation_manifest,
)


def _statement(
    *,
    kind: str = "alter_column_type",
    schema_name: str = "Sales Data",
    table_name: str = 'Order "Item"',
    precondition_schema: str | None = None,
    precondition_table: str | None = None,
) -> dict[str, object]:
    """Build one exact compiler-v1 statement with a data precondition."""

    return {
        "kind": kind,
        "target": f"{schema_name}.{table_name}.amount",
        "object_ref": {
            "schema_name": schema_name,
            "table_name": table_name,
            "column_name": "amount",
        },
        "sql": "server-owned and never parsed by this boundary",
        "transactional": True,
        "dependencies": [],
        "dependency_refs": [],
        "reversible": False,
        "risk": {
            "severity": "warning",
            "lock_mode": "ACCESS EXCLUSIVE",
            "possible_rewrite": True,
            "table_scan": True,
            "data_loss": False,
            "detail": "bounded test fixture",
        },
        "required_privileges": ["ALTER"],
        "preconditions": [
            {
                "kind": "no_null_values",
                "schema_name": precondition_schema or schema_name,
                "table_name": precondition_table or table_name,
                "column_name": "amount",
            }
        ],
    }


def _signed_plan(*statements: dict[str, object]) -> dict[str, object]:
    """Build and sign the exact immutable plan shape used by compiler v1."""

    plan: dict[str, object] = {
        "compiler_version": COMPILER_VERSION,
        "snapshot_contract_version": 1,
        "postgresql_major": 18,
        "base_digest": "a" * 64,
        "target_digest": "b" * 64,
        "statements": list(statements),
        "proposed_statements": [],
        "blockers": [],
        "risk_summary": {"safe": 0, "warning": len(statements), "destructive": 0},
        "requires_destructive_confirmation": False,
        "can_dry_run": True,
    }
    encoded = json.dumps(
        plan,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    plan["plan_digest"] = hashlib.sha256(encoded).hexdigest()
    return plan


def _resign(plan: dict[str, object]) -> None:
    """Replace the claimed digest after an intentional fixture mutation."""

    plan.pop("plan_digest", None)
    encoded = json.dumps(
        plan,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    plan["plan_digest"] = hashlib.sha256(encoded).hexdigest()


def test_binds_signed_plan_locks_and_checks_without_target_access() -> None:
    """Manifest preserves exact authority inputs and deterministic ordering."""

    plan = _signed_plan(_statement())

    manifest = compile_pre_apply_revalidation_manifest(
        plan, expected_plan_digest=plan["plan_digest"]
    )

    assert manifest.plan_digest == plan["plan_digest"]
    assert manifest.compiler_version == COMPILER_VERSION
    assert manifest.snapshot_contract_version == 1
    assert manifest.postgresql_major == 18
    assert manifest.base_digest == "a" * 64
    assert manifest.target_digest == "b" * 64
    assert [target.sql for target in manifest.lock_targets] == [
        'LOCK TABLE "Sales Data"."Order ""Item""" IN ACCESS EXCLUSIVE MODE'
    ]
    assert [query.sql for query in manifest.precondition_queries] == [
        'SELECT NOT EXISTS (SELECT 1 FROM "Sales Data"."Order ""Item""" '
        'WHERE "amount" IS NULL LIMIT 1)'
    ]


def test_rejects_content_that_no_longer_matches_the_stored_digest() -> None:
    """A caller cannot bind lock/check work from mutated plan content."""

    plan = _signed_plan(_statement())
    expected_digest = plan["plan_digest"]
    plan["postgresql_major"] = 17

    with pytest.raises(
        PreApplyRevalidationContractError, match="plan digest is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=expected_digest
        )


def test_rejects_noncanonical_plan_content_with_a_fixed_error() -> None:
    """Digest verification never exposes serialization implementation detail."""

    plan = _signed_plan(_statement())
    plan["risk_summary"] = {"warning": {1}}

    with pytest.raises(
        PreApplyRevalidationContractError, match="plan digest is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest="a" * 64
        )


@pytest.mark.parametrize("expected_digest", [None, True, "A" * 64, "a" * 63])
def test_rejects_invalid_expected_plan_digest(expected_digest: object) -> None:
    """Stored digest input must be a canonical lowercase SHA-256 value."""

    plan = _signed_plan(_statement())

    with pytest.raises(
        PreApplyRevalidationContractError, match="expected plan digest is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=expected_digest
        )


def test_rejects_unknown_plan_fields_even_when_the_content_is_signed() -> None:
    """A future contract cannot silently enter a compiler-v1 apply boundary."""

    plan = _signed_plan(_statement())
    plan["future_authority"] = True
    _resign(plan)

    with pytest.raises(
        PreApplyRevalidationContractError, match="plan contract is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )


def test_rejects_precondition_bound_to_a_different_table() -> None:
    """Every data check must describe the statement's structured table ref."""

    plan = _signed_plan(
        _statement(precondition_schema="other", precondition_table="orders")
    )

    with pytest.raises(
        PreApplyRevalidationContractError,
        match="precondition target does not match statement",
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )


def test_rejects_preconditions_without_an_existing_table_lock() -> None:
    """A data check cannot be scheduled unless its relation will be locked."""

    plan = _signed_plan(_statement(kind="create_table"))

    with pytest.raises(
        PreApplyRevalidationContractError, match="precondition target is not locked"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("compiler_version", "future", "compiler is unsupported"),
        (
            "snapshot_contract_version",
            2,
            "snapshot contract is unsupported",
        ),
        ("proposed_statements", [{}], "proposals are not executable"),
    ],
)
def test_rejects_incompatible_or_review_only_plan_contracts(
    field: str, value: object, message: str
) -> None:
    """Only exact executable compiler-v1 plans can produce a manifest."""

    plan = _signed_plan(_statement())
    plan[field] = value
    _resign(plan)

    with pytest.raises(PreApplyRevalidationContractError, match=message):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )


@pytest.mark.parametrize("postgresql_major", [True, 13, 19, "18"])
def test_rejects_unsupported_postgresql_major(postgresql_major: object) -> None:
    """Manifest compatibility remains bounded to supported PostgreSQL majors."""

    plan = _signed_plan(_statement())
    plan["postgresql_major"] = postgresql_major
    _resign(plan)

    with pytest.raises(
        PreApplyRevalidationContractError, match="PostgreSQL major is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )
