from __future__ import annotations

from app.spec.schema_docs_html import render_schema_docs_html

SNAP = {
    "relations": [
        {"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "member", "relation_comment": "회원"},
        {"relation_oid": 2, "relation_kind": "v", "schema_name": "public", "relation_name": "v_report"},
    ],
    "columns": [
        {"relation_oid": 1, "column_name": "member_id", "column_position": 1, "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 1, "column_name": "email", "column_position": 2, "data_type": "text", "is_not_null": False, "column_comment": "로그인 이메일"},
    ],
    "pk_columns": [{"relation_oid": 1, "column_name": "member_id"}],
    "fk_edges": [],
}


def test_renders_tables_columns_badges_and_comments():
    page = render_schema_docs_html(SNAP, title="My Schema")
    assert "<title>My Schema</title>" in page
    assert "public.member" in page
    assert "회원" in page and "로그인 이메일" in page
    assert "class='badge pk'" in page  # member_id PK badge
    assert "(view)" in page  # v_report labelled


def test_fk_badge_points_to_parent():
    snap = {**SNAP, "relations": SNAP["relations"] + [
        {"relation_oid": 3, "relation_kind": "r", "schema_name": "public", "relation_name": "orders"},
    ], "columns": SNAP["columns"] + [
        {"relation_oid": 3, "column_name": "member_id", "column_position": 1, "data_type": "bigint", "is_not_null": True},
    ], "fk_edges": [
        {"child_relation_oid": 3, "parent_relation_oid": 1,
         "child_column_name": "member_id", "parent_column_name": "member_id"},
    ]}
    page = render_schema_docs_html(snap)
    assert "FK → public.member.member_id" in page


def test_everything_is_escaped_no_script_injection():
    hostile = {
        "relations": [{"relation_oid": 1, "relation_kind": "r", "schema_name": "public",
                       "relation_name": "<script>alert(1)</script>",
                       "relation_comment": '<img src=x onerror=alert(2)>'}],
        "columns": [{"relation_oid": 1, "column_name": '"><script>x</script>',
                     "column_position": 1, "data_type": "<b>text</b>", "is_not_null": False}],
        "pk_columns": [], "fk_edges": [],
    }
    page = render_schema_docs_html(hostile)
    assert "<script>" not in page
    assert "onerror=" not in page or "&lt;img" in page  # escaped form only
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    # page itself contains no script tags at all
    assert page.lower().count("<script") == 0


def test_empty_snapshot_still_valid_page():
    page = render_schema_docs_html(None)
    assert page.startswith("<!doctype html>")
    assert "0 relations" in page
