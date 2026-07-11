from __future__ import annotations

from app.spec.audit_columns import check_audit_columns


def _snap(tables):
    """tables: {name: [column, ...]}"""
    relations, columns = [], []
    for oid, (t, cols) in enumerate(tables.items(), start=1):
        relations.append({"relation_oid": oid, "relation_kind": "r", "schema_name": "public", "relation_name": t})
        for c in cols:
            columns.append({"relation_oid": oid, "column_name": c})
    return {"relations": relations, "columns": columns}


def test_flags_outlier_when_majority_has_audit_columns():
    snap = _snap({
        "a": ["id", "created_at", "updated_at"],
        "b": ["id", "created_at", "updated_at"],
        "c": ["id", "created_at", "updated_at"],
        "d": ["id"],  # outlier
    })
    report = check_audit_columns(snap)
    assert report["summary"]["convention_active"] is True
    assert len(report["items"]) == 1
    item = report["items"][0]
    assert item["table"] == "public.d"
    assert set(item["missing"]) == {"created_at", "updated_at"}


def test_no_flags_when_schema_has_no_convention():
    snap = _snap({
        "a": ["id"], "b": ["id"], "c": ["id"], "d": ["id", "created_at"],
    })
    report = check_audit_columns(snap)  # 25% adoption < 50%
    assert report["items"] == []
    assert report["summary"]["convention_active"] is False


def test_variant_names_count_as_audit_columns():
    snap = _snap({
        "a": ["id", "create_time", "modified_at"],
        "b": ["id", "reg_dt", "last_modified"],
        "c": ["id", "inserted_at", "update_dt"],
        "d": ["id", "created_on", "updated_on"],
    })
    report = check_audit_columns(snap)
    assert report["items"] == []  # all four satisfy both via variants
    assert report["summary"]["with_created"] == 4
    assert report["summary"]["with_updated"] == 4


def test_small_schemas_are_not_judged_and_empty():
    snap = _snap({"a": ["id", "created_at"], "b": ["id"]})  # only 2 tables
    assert check_audit_columns(snap)["items"] == []
    assert check_audit_columns({})["summary"]["tables"] == 0
