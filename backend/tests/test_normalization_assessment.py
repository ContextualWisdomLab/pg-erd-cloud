"""Golden-fixture tests for :mod:`app.spec.normalization_assessment`.

Each fixture is a hand-built schema snapshot whose expected normalization
classification and evidence class are known from relational theory, so a
regression changes an exact asserted value rather than a fuzzy score.
"""

from __future__ import annotations

from typing import Any

from app.spec.normalization_assessment import (
    ASSESSMENT_VERSION,
    assess_normalization,
)


def _column(
    oid: int,
    position: int,
    name: str,
    data_type: str,
    *,
    not_null: bool = False,
    type_category: str = "",
    array_dimensions: int = 0,
) -> dict[str, Any]:
    """Build one column record in the introspection snapshot shape."""

    return {
        "relation_oid": oid,
        "column_position": position,
        "column_name": name,
        "data_type": data_type,
        "is_not_null": not_null,
        "type_category": type_category,
        "array_dimensions": array_dimensions,
    }


def _relation(oid: int, name: str, *, kind: str = "r", schema: str = "public") -> dict[str, Any]:
    """Build one relation record in the introspection snapshot shape."""

    return {
        "relation_oid": oid,
        "schema_name": schema,
        "relation_name": name,
        "relation_kind": kind,
    }


def _find(result: dict[str, Any], relation: str, kind: str) -> dict[str, Any] | None:
    """Return the first finding for ``relation``/``kind`` or ``None``."""

    for finding in result["findings"]:
        if finding["relation"]["name"] == relation and finding["kind"] == kind:
            return finding
    return None


def _assessment(result: dict[str, Any], relation: str) -> dict[str, Any]:
    """Return the relation assessment record for ``relation``."""

    for record in result["relation_assessments"]:
        if record["relation"]["name"] == relation:
            return record
    raise AssertionError(f"no assessment for {relation!r}")


def test_clean_single_key_table_is_bcnf_with_no_findings() -> None:
    snapshot = {
        "relations": [_relation(1, "app_user")],
        "columns": [
            _column(1, 1, "user_id", "bigint", not_null=True),
            _column(1, 2, "email_address", "text", not_null=True),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "user_id"}],
    }
    result = assess_normalization(snapshot)
    assert result["version"] == ASSESSMENT_VERSION
    assert result["evidence_basis"] == "catalog_only"
    assert result["findings"] == []
    record = _assessment(result, "app_user")
    assert record["normal_form"] == "bcnf"
    assert record["evidence_class"] == "declared"
    assert record["candidate_keys"] == [["user_id"]]
    assert record["non_prime_columns"] == ["email_address"]


def test_array_column_is_a_high_confidence_1nf_observation() -> None:
    snapshot = {
        "relations": [_relation(1, "survey_response")],
        "columns": [
            _column(1, 1, "response_id", "bigint", not_null=True),
            _column(1, 2, "answer_codes", "integer[]", type_category="A", array_dimensions=1),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "response_id"}],
    }
    result = assess_normalization(snapshot)
    finding = _find(result, "survey_response", "non_atomic_column")
    assert finding is not None
    assert finding["normal_form_scope"] == "1NF"
    assert finding["evidence_class"] == "observed"
    assert finding["confidence"] == "high"
    assert finding["source_objects"] == [{"type": "column", "name": "answer_codes"}]
    assert _assessment(result, "survey_response")["normal_form"] == "1nf_review"


def test_jsonb_column_is_a_medium_confidence_1nf_observation() -> None:
    snapshot = {
        "relations": [_relation(1, "schema_snapshot_data")],
        "columns": [
            _column(1, 1, "snapshot_id", "bigint", not_null=True),
            _column(1, 2, "snapshot_json", "jsonb", not_null=True),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "snapshot_id"}],
    }
    result = assess_normalization(snapshot)
    finding = _find(result, "schema_snapshot_data", "non_atomic_column")
    assert finding is not None
    assert finding["confidence"] == "medium"
    assert "evidence envelope" in finding["false_positive_caveat"]


def test_missing_candidate_key_yields_insufficient_evidence() -> None:
    snapshot = {
        "relations": [_relation(1, "import_staging")],
        "columns": [
            _column(1, 1, "raw_line", "text"),
            _column(1, 2, "loaded_at", "timestamptz"),
        ],
    }
    result = assess_normalization(snapshot)
    finding = _find(result, "import_staging", "missing_candidate_key")
    assert finding is not None
    assert finding["evidence_class"] == "inferred"
    assert finding["confidence"] == "high"
    record = _assessment(result, "import_staging")
    assert record["normal_form"] == "insufficient_evidence"
    assert record["candidate_keys"] == []


def test_nullable_unique_is_a_declared_bcnf_finding_not_a_candidate_key() -> None:
    snapshot = {
        "relations": [_relation(1, "billing_account")],
        "columns": [
            _column(1, 1, "account_id", "bigint", not_null=True),
            _column(1, 2, "external_reference", "text"),  # nullable
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "account_id"}],
        "constraints": [
            {
                "relation_oid": 1,
                "constraint_type": "u",
                "constraint_name": "billing_account_external_reference_key",
                "constrained_attnums": [2],
            }
        ],
    }
    result = assess_normalization(snapshot)
    finding = _find(result, "billing_account", "nullable_unique_determinant")
    assert finding is not None
    assert finding["evidence_class"] == "declared"
    record = _assessment(result, "billing_account")
    assert record["normal_form"] == "bcnf_review"
    assert record["candidate_keys"] == [["account_id"]]  # the nullable UNIQUE is excluded


def test_not_null_unique_becomes_a_candidate_key() -> None:
    snapshot = {
        "relations": [_relation(1, "billing_account")],
        "columns": [
            _column(1, 1, "account_id", "bigint", not_null=True),
            _column(1, 2, "external_reference", "text", not_null=True),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "account_id"}],
        "constraints": [
            {
                "relation_oid": 1,
                "constraint_type": "u",
                "constraint_name": "billing_account_external_reference_key",
                "constrained_attnums": [2],
            }
        ],
    }
    result = assess_normalization(snapshot)
    assert _find(result, "billing_account", "nullable_unique_determinant") is None
    record = _assessment(result, "billing_account")
    assert record["normal_form"] == "bcnf"
    assert ["external_reference"] in record["candidate_keys"]
    assert record["non_prime_columns"] == []


def test_composite_key_with_extra_column_flags_partial_dependency_precondition() -> None:
    snapshot = {
        "relations": [_relation(1, "order_line")],
        "columns": [
            _column(1, 1, "order_id", "bigint", not_null=True),
            _column(1, 2, "product_id", "bigint", not_null=True),
            _column(1, 3, "product_name", "text", not_null=True),
            _column(1, 4, "quantity", "integer", not_null=True),
        ],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "order_id"},
            {"relation_oid": 1, "column_name": "product_id"},
        ],
    }
    result = assess_normalization(snapshot)
    finding = _find(result, "order_line", "partial_dependency_precondition")
    assert finding is not None
    assert finding["normal_form_scope"] == "2NF"
    assert finding["evidence_class"] == "inferred"
    assert finding["confidence"] == "low"
    assert set(o["name"] for o in finding["source_objects"]) == {"product_name", "quantity"}
    assert _assessment(result, "order_line")["normal_form"] == "2nf_review"


def test_pure_junction_table_with_only_key_columns_is_bcnf() -> None:
    snapshot = {
        "relations": [_relation(1, "role_permission")],
        "columns": [
            _column(1, 1, "role_id", "bigint", not_null=True),
            _column(1, 2, "permission_id", "bigint", not_null=True),
        ],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "role_id"},
            {"relation_oid": 1, "column_name": "permission_id"},
        ],
    }
    result = assess_normalization(snapshot)
    assert _find(result, "role_permission", "partial_dependency_precondition") is None
    assert _assessment(result, "role_permission")["normal_form"] == "bcnf"


def test_composite_key_plus_single_column_key_suppresses_partial_dependency() -> None:
    snapshot = {
        "relations": [_relation(1, "order_line")],
        "columns": [
            _column(1, 1, "line_id", "bigint", not_null=True),
            _column(1, 2, "order_id", "bigint", not_null=True),
            _column(1, 3, "product_id", "bigint", not_null=True),
            _column(1, 4, "quantity", "integer", not_null=True),
        ],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "order_id"},
            {"relation_oid": 1, "column_name": "product_id"},
        ],
        "constraints": [
            {
                "relation_oid": 1,
                "constraint_type": "u",
                "constraint_name": "order_line_line_id_key",
                "constrained_attnums": [1],
            }
        ],
    }
    result = assess_normalization(snapshot)
    assert _find(result, "order_line", "partial_dependency_precondition") is None
    assert _assessment(result, "order_line")["normal_form"] == "bcnf"


def test_waiver_records_a_finding_as_waived_and_relaxes_the_label() -> None:
    snapshot = {
        "relations": [_relation(1, "schema_snapshot_data")],
        "columns": [
            _column(1, 1, "snapshot_id", "bigint", not_null=True),
            _column(1, 2, "snapshot_json", "jsonb", not_null=True),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "snapshot_id"}],
    }
    waivers = [
        {
            "scope": {"schema": "public", "relation": "schema_snapshot_data", "kind": "non_atomic_column"},
            "owner": "data-platform",
            "reason": "immutable schema payload is a deliberate evidence envelope, not a repeating group",
            "review_date": "2026-09-01",
            "expiry": "2027-03-01",
        }
    ]
    result = assess_normalization(snapshot, waivers=waivers)
    finding = _find(result, "schema_snapshot_data", "non_atomic_column")
    assert finding is not None
    assert finding["evidence_class"] == "waived"
    assert finding["waiver"]["owner"] == "data-platform"
    # A waived finding no longer drives the relation label.
    assert _assessment(result, "schema_snapshot_data")["normal_form"] == "bcnf"


def test_waiver_with_empty_scope_never_matches() -> None:
    snapshot = {
        "relations": [_relation(1, "survey_response")],
        "columns": [
            _column(1, 1, "response_id", "bigint", not_null=True),
            _column(1, 2, "answer_codes", "integer[]", type_category="A", array_dimensions=1),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "response_id"}],
    }
    result = assess_normalization(snapshot, waivers=[{"scope": {}, "owner": "x", "reason": "y"}])
    finding = _find(result, "survey_response", "non_atomic_column")
    assert finding is not None
    assert finding["evidence_class"] == "observed"


def test_views_are_not_assessed() -> None:
    snapshot = {
        "relations": [_relation(1, "active_user_v", kind="v")],
        "columns": [_column(1, 1, "user_id", "bigint")],
    }
    result = assess_normalization(snapshot)
    assert result["relation_assessments"] == []
    assert result["findings"] == []


def test_empty_and_none_snapshots_are_stable() -> None:
    empty = {"version": ASSESSMENT_VERSION, "evidence_basis": "catalog_only", "relation_assessments": [], "findings": []}
    assert assess_normalization(None) == empty
    assert assess_normalization({}) == empty


def test_output_is_deterministic_across_runs() -> None:
    snapshot = {
        "relations": [_relation(2, "b_table"), _relation(1, "a_table")],
        "columns": [
            _column(1, 1, "a_id", "bigint", not_null=True),
            _column(1, 2, "payload", "jsonb"),
            _column(2, 1, "raw", "text"),
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "a_id"}],
    }
    first = assess_normalization(snapshot)
    second = assess_normalization(snapshot)
    assert first == second
    names = [f["relation"]["name"] for f in first["findings"]]
    assert names == sorted(names)
