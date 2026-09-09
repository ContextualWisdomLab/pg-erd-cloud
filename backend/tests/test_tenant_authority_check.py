"""Tests for :mod:`app.deploy.tenant_authority_check`.

The check must partition every authority-bearing object into carrying /
derived / missing, treat ``single_org_per_database`` as not-applicable, and
reject an unknown isolation mode.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.deploy.profile import AUTHORITY_BEARING_OBJECTS
from app.deploy.tenant_authority_check import (
    CHECK_VERSION,
    TENANT_KEY_COLUMN,
    check_tenant_authority,
)


def _all_carrying() -> list[dict[str, Any]]:
    """Every authority object, each carrying the tenant key column."""
    return [
        {"name": obj, "columns": ["id", TENANT_KEY_COLUMN]}
        for obj in AUTHORITY_BEARING_OBJECTS
    ]


def test_single_org_per_database_is_not_applicable() -> None:
    report = check_tenant_authority([], tenant_isolation="single_org_per_database")
    assert report["applicable"] is False
    assert report["compliant"] is True
    assert "not_applicable_reason" in report
    assert report["version"] == CHECK_VERSION


def test_all_objects_carrying_the_key_is_compliant() -> None:
    report = check_tenant_authority(
        _all_carrying(), tenant_isolation="shared_db_tenant_scoped_rows"
    )
    assert report["applicable"] is True
    assert report["compliant"] is True
    assert sorted(report["carrying"]) == sorted(AUTHORITY_BEARING_OBJECTS)
    assert report["missing_scoping"] == []
    assert report["missing_definition"] == []
    assert report["required_object_count"] == len(AUTHORITY_BEARING_OBJECTS)


def test_a_missing_definition_is_reported_and_fails() -> None:
    defs = _all_carrying()[1:]  # drop the first authority object entirely
    report = check_tenant_authority(
        defs, tenant_isolation="shared_db_tenant_scoped_rows"
    )
    assert report["compliant"] is False
    assert report["missing_definition"] == [AUTHORITY_BEARING_OBJECTS[0]]


def test_a_table_without_the_key_or_a_derivation_fails() -> None:
    defs = _all_carrying()
    defs[2] = {"name": AUTHORITY_BEARING_OBJECTS[2], "columns": ["id", "label"]}
    report = check_tenant_authority(
        defs, tenant_isolation="shared_db_tenant_scoped_rows"
    )
    assert report["compliant"] is False
    assert report["missing_scoping"] == [AUTHORITY_BEARING_OBJECTS[2]]


def test_a_derived_table_counts_as_scoped() -> None:
    defs = _all_carrying()
    defs[3] = {
        "name": AUTHORITY_BEARING_OBJECTS[3],
        "columns": ["id", "parent_id"],
        "derives_tenant_from": AUTHORITY_BEARING_OBJECTS[0],
    }
    report = check_tenant_authority(
        defs, tenant_isolation="shared_db_tenant_scoped_rows"
    )
    assert report["compliant"] is True
    assert {"object": AUTHORITY_BEARING_OBJECTS[3], "via": AUTHORITY_BEARING_OBJECTS[0]} in report[
        "derived"
    ]
    assert AUTHORITY_BEARING_OBJECTS[3] not in report["carrying"]


def test_unknown_tables_are_listed_but_do_not_fail() -> None:
    defs = _all_carrying() + [
        {"name": "some_lookup_table", "columns": ["id"]},
        {"name": "another_helper", "columns": ["id", TENANT_KEY_COLUMN]},
    ]
    report = check_tenant_authority(
        defs, tenant_isolation="shared_db_tenant_scoped_rows"
    )
    assert report["compliant"] is True
    assert report["unknown_tables"] == ["another_helper", "some_lookup_table"]


def test_entries_without_a_name_are_skipped() -> None:
    defs = _all_carrying() + [{"columns": ["id"]}, {"name": "", "columns": []}]
    report = check_tenant_authority(
        defs, tenant_isolation="shared_db_tenant_scoped_rows"
    )
    assert report["compliant"] is True


def test_empty_definitions_report_every_object_missing() -> None:
    report = check_tenant_authority(
        [], tenant_isolation="shared_db_tenant_scoped_rows"
    )
    assert report["compliant"] is False
    assert sorted(report["missing_definition"]) == sorted(AUTHORITY_BEARING_OBJECTS)
    assert report["carrying"] == []


def test_unknown_isolation_mode_raises_value_error() -> None:
    with pytest.raises(ValueError):
        check_tenant_authority([], tenant_isolation="magic")  # type: ignore[arg-type]


def test_output_is_deterministic() -> None:
    defs = _all_carrying()
    defs[5] = {"name": AUTHORITY_BEARING_OBJECTS[5], "columns": ["id"]}
    a = check_tenant_authority(defs, tenant_isolation="shared_db_tenant_scoped_rows")
    b = check_tenant_authority(defs, tenant_isolation="shared_db_tenant_scoped_rows")
    assert a == b


def test_module_carries_no_performance_threshold_literal() -> None:
    import re
    from pathlib import Path

    src = Path("app/deploy/tenant_authority_check.py").read_text(encoding="utf-8").lower()
    assert re.search(r"\b\d+(\.\d+)?\s*(ms|milliseconds|seconds)\b", src) is None
    assert re.search(r"p9[59]\s*[<>=:]", src) is None
