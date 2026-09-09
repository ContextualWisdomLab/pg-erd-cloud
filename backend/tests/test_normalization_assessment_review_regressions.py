"""Focused regressions for normalization-assessment review findings."""

from __future__ import annotations

from app.mysql_introspect.introspect import rows_to_snapshot
from app.spec.normalization_assessment import assess_normalization


def test_mysql_functional_unique_index_does_not_abort_or_become_column_key() -> None:
    """Unrepresentable functional indexes must not become common column keys."""

    snapshot = rows_to_snapshot(
        "8.4.0",
        None,
        [
            {
                "TABLE_SCHEMA": "shop",
                "TABLE_NAME": "member",
                "TABLE_TYPE": "BASE TABLE",
                "TABLE_COMMENT": "",
            }
        ],
        [
            {
                "TABLE_SCHEMA": "shop",
                "TABLE_NAME": "member",
                "COLUMN_NAME": "member_id",
                "ORDINAL_POSITION": 1,
                "COLUMN_TYPE": "bigint",
                "DATA_TYPE": "bigint",
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "COLUMN_COMMENT": "",
            },
            {
                "TABLE_SCHEMA": "shop",
                "TABLE_NAME": "member",
                "COLUMN_NAME": "email_address",
                "ORDINAL_POSITION": 2,
                "COLUMN_TYPE": "varchar(255)",
                "DATA_TYPE": "varchar",
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "COLUMN_COMMENT": "",
            },
        ],
        [
            {
                "CONSTRAINT_NAME": "PRIMARY",
                "TABLE_SCHEMA": "shop",
                "TABLE_NAME": "member",
                "COLUMN_NAME": "member_id",
                "ORDINAL_POSITION": 1,
                "REFERENCED_TABLE_SCHEMA": None,
                "REFERENCED_TABLE_NAME": None,
                "REFERENCED_COLUMN_NAME": None,
            }
        ],
        [
            {
                "TABLE_SCHEMA": "shop",
                "TABLE_NAME": "member",
                "INDEX_NAME": "ux_member_lower_email",
                "NON_UNIQUE": 0,
                "SEQ_IN_INDEX": 1,
                "COLUMN_NAME": None,
            }
        ],
    )

    assert not any(
        constraint["constraint_type"] == "u"
        and constraint["constraint_name"] == "ux_member_lower_email"
        for constraint in snapshot["constraints"]
    )


def test_duplicate_nullable_unique_constraints_have_distinct_finding_ids() -> None:
    """Constraint identity must distinguish findings over the same columns."""

    snapshot = {
        "relations": [
            {
                "relation_oid": 1,
                "schema_name": "public",
                "relation_name": "billing_account",
                "relation_kind": "r",
            }
        ],
        "columns": [
            {
                "relation_oid": 1,
                "column_position": 1,
                "column_name": "account_id",
                "data_type": "bigint",
                "is_not_null": True,
            },
            {
                "relation_oid": 1,
                "column_position": 2,
                "column_name": "external_reference",
                "data_type": "text",
                "is_not_null": False,
            },
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "account_id"}],
        "constraints": [
            {
                "relation_oid": 1,
                "constraint_type": "u",
                "constraint_name": "billing_account_reference_a_key",
                "constrained_attnums": [2],
            },
            {
                "relation_oid": 1,
                "constraint_type": "u",
                "constraint_name": "billing_account_reference_b_key",
                "constrained_attnums": [2],
            },
        ],
    }

    findings = [
        finding
        for finding in assess_normalization(snapshot)["findings"]
        if finding["kind"] == "nullable_unique_determinant"
    ]
    assert len(findings) == 2
    assert len({finding["finding_id"] for finding in findings}) == 2
