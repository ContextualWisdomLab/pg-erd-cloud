from __future__ import annotations

from app.spec.naming_lint import lint_naming


def _snap(tables):
    """tables: {relation_name: [column_name, ...]}"""
    relations, columns = [], []
    for oid, (t, cols) in enumerate(tables.items(), start=1):
        relations.append({"relation_oid": oid, "schema_name": "public", "relation_name": t})
        for c in cols:
            columns.append({"relation_oid": oid, "column_name": c})
    return {"relations": relations, "columns": columns}


def _cats(report):
    return {(i["category"], i["severity"]) for i in report["items"]}


def test_flags_reserved_word_table_and_column():
    report = lint_naming(_snap({"order": ["id"], "member": ["user"]}))
    cats = _cats(report)
    assert ("reserved_word", "high") in cats
    # both 'order' (table) and 'user' (column) are reserved
    assert report["summary"]["high"] >= 2


def test_flags_identifier_requiring_quotes():
    report = lint_naming(_snap({"MyTable": ["id"], "member": ["first-name", "2fa_flag"]}))
    cats = _cats(report)
    assert ("requires_quoting", "high") in cats
    targets = {i["target"] for i in report["items"] if i["category"] == "requires_quoting"}
    assert any("MyTable" in t for t in targets)  # uppercase
    assert any("first-name" in t for t in targets)  # hyphen
    assert any("2fa_flag" in t for t in targets)  # leading digit


def test_flags_case_inconsistency_against_dominant_style():
    # mostly snake_case, one camelCase outlier
    report = lint_naming(_snap({
        "member": ["member_id", "created_at"],
        "orders": ["order_id", "createdAt"],
    }))
    assert ("inconsistent_case", "info") in _cats(report)
    assert report["summary"]["dominant_case"] == "snake"


def test_clean_snake_case_schema_has_no_findings():
    report = lint_naming(_snap({
        "member": ["member_id", "email", "created_at"],
        "orders": ["order_id", "member_id", "created_at"],
    }))
    assert report["items"] == []


def test_my_own_new_tables_pass_the_lint():
    """Dog-fooding: the tables this project added must not violate the lint."""
    report = lint_naming(_snap({
        "diagram_view": ["diagram_view_uuid", "project_space_uuid", "name",
                          "layout_json", "created_by", "created_at", "updated_at"],
        "table_annotation": ["table_annotation_uuid", "project_space_uuid",
                             "schema_name", "relation_name", "body",
                             "created_by", "created_at", "updated_at"],
    }))
    assert report["summary"]["high"] == 0, report["items"]
