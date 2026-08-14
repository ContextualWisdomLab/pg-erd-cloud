"""Deterministic pre-apply table-lock planning contract tests."""

from __future__ import annotations

import pytest

from app.forward.apply_lock_plan import (
    ApplyLockPlanContractError,
    compile_apply_lock_targets,
)
from app.forward.migration_plan import COMPILER_VERSION


def _statement(
    kind: str,
    schema_name: object,
    table_name: object,
    *,
    lock_mode: object = "ACCESS EXCLUSIVE",
    transactional: object = True,
) -> dict[str, object]:
    """Build one structured statement without depending on rendered SQL."""

    return {
        "kind": kind,
        "object_ref": {
            "schema_name": schema_name,
            "table_name": table_name,
        },
        "risk": {"lock_mode": lock_mode},
        "transactional": transactional,
    }


def _plan(*statements: dict[str, object]) -> dict[str, object]:
    """Build one executable single-segment plan."""

    return {
        "compiler_version": COMPILER_VERSION,
        "blockers": [],
        "can_dry_run": True,
        "statements": list(statements),
    }


def test_compiles_sorted_unique_existing_table_locks_without_sql_reparsing() -> None:
    """Lock targets come only from structured refs and use deterministic order."""

    plan = _plan(
        _statement("add_column", "zeta", "orders"),
        _statement("drop_column", "alpha", 'Order "Item"'),
        _statement("set_not_null", "zeta", "orders"),
        _statement("create_table", "alpha", "new_table"),
        {
            "kind": "create_schema",
            "object_ref": {"schema_name": "new_schema"},
            "risk": {"lock_mode": "none"},
            "transactional": True,
        },
    )

    targets = compile_apply_lock_targets(plan)

    assert [
        (target.schema_name, target.table_name, target.sql) for target in targets
    ] == [
        (
            "alpha",
            'Order "Item"',
            'LOCK TABLE "alpha"."Order ""Item""" IN ACCESS EXCLUSIVE MODE',
        ),
        (
            "zeta",
            "orders",
            'LOCK TABLE "zeta"."orders" IN ACCESS EXCLUSIVE MODE',
        ),
    ]


def test_preserves_mixed_case_and_unicode_identifiers() -> None:
    """PostgreSQL delimited identifiers retain exact reviewed spelling."""

    (target,) = compile_apply_lock_targets(
        _plan(_statement("drop_table", "영업 Schema", "MixedCase"))
    )

    assert target.sql == (
        'LOCK TABLE "영업 Schema"."MixedCase" IN ACCESS EXCLUSIVE MODE'
    )


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        (
            {
                "compiler_version": "future",
                "blockers": [],
                "can_dry_run": True,
                "statements": [],
            },
            "compiler is unsupported",
        ),
        (
            {
                "blockers": [],
                "can_dry_run": True,
                "statements": [],
            },
            "compiler is unsupported",
        ),
        (
            {
                "compiler_version": COMPILER_VERSION,
                "blockers": [{"code": "blocked"}],
                "can_dry_run": False,
                "statements": [],
            },
            "cannot enter apply lock planning",
        ),
        (
            _plan(_statement("create_index_concurrently", "public", "orders")),
            "unsupported apply statement kind",
        ),
        (
            _plan(_statement("add_column", "public", "orders", transactional=False)),
            "must be transactional",
        ),
        (
            _plan(_statement("add_column", "public", "orders", lock_mode="SHARE")),
            "lock mode is invalid",
        ),
        (
            _plan(_statement("drop_table", "bad\x00schema", "orders")),
            "identifier is invalid",
        ),
        (
            _plan(_statement("drop_table", "public", "x" * 64)),
            "identifier is too large",
        ),
    ],
)
def test_fails_closed_for_non_executable_or_tampered_lock_inputs(
    plan: dict[str, object], message: str
) -> None:
    """Malformed or unsupported plan metadata never produces lock SQL."""

    with pytest.raises(ApplyLockPlanContractError, match=message):
        compile_apply_lock_targets(plan)


def test_rejects_more_than_the_bounded_statement_count() -> None:
    """A tampered oversized plan cannot bypass lock planning with new objects."""

    statements = [
        {
            "kind": "create_schema",
            "object_ref": {"schema_name": f"schema_{index}"},
            "risk": {"lock_mode": "none"},
            "transactional": True,
        }
        for index in range(1001)
    ]

    with pytest.raises(ApplyLockPlanContractError, match="too many statements"):
        compile_apply_lock_targets(_plan(*statements))
