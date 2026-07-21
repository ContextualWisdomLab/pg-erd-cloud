from __future__ import annotations

from app.ddl.export import snapshot_json_to_sql
from app.spec.dbml_import import parse_dbml

BASIC = """
// a typical dbdiagram.io document
Table users {
  id integer [pk, not null]
  username varchar(255) [not null, unique]
  created_at timestamp
}

Table posts {
  id integer [pk]
  user_id integer [not null, ref: > users.id]
  title varchar
}

Ref: posts.user_id > users.id
"""


def test_parses_tables_columns_pks():
    snap = parse_dbml(BASIC)
    names = {(r["schema_name"], r["relation_name"]) for r in snap["relations"]}
    assert names == {("public", "users"), ("public", "posts")}
    cols = {c["column_name"] for c in snap["columns"] if c["relation_oid"] == 1}
    assert cols == {"id", "username", "created_at"}
    # pk implies not null; plain column stays nullable
    by_name = {c["column_name"]: c for c in snap["columns"]}
    assert by_name["id"]["is_not_null"] is True
    assert by_name["created_at"]["is_not_null"] is False
    assert {p["column_name"] for p in snap["pk_columns"]} == {"id"}


def test_parses_refs_inline_and_standalone_deduped_semantics():
    snap = parse_dbml(BASIC)
    # inline ref + standalone ref both point posts.user_id -> users.id
    assert all(
        e["child_column_name"] == "user_id" and e["parent_column_name"] == "id"
        for e in snap["fk_edges"]
    )
    assert len(snap["fk_edges"]) == 1  # parser is literal; dedup is the caller's choice


def test_reverse_arrow_and_schema_qualified_and_quoted():
    text = '''
Table auth.accounts {
  account_id bigint [pk]
}
Table "Order Items" {
  id bigint [pk]
  account_id bigint
}
Ref: auth.accounts.account_id < "Order Items".account_id
'''
    snap = parse_dbml(text)
    assert ("auth", "accounts") in {(r["schema_name"], r["relation_name"]) for r in snap["relations"]}
    edge = snap["fk_edges"][0]
    # '<' means the right side references the left
    child = next(r for r in snap["relations"] if r["relation_oid"] == edge["child_relation_oid"])
    assert child["relation_name"] == "Order Items"


def test_ignores_project_enum_notes_and_unknown_refs():
    text = """
Project demo {
  database_type: 'PostgreSQL'
}
Enum status {
  active
  banned
}
Table t {
  id int [pk]
  s status
}
Ref: t.ghost_col > missing_table.id
"""
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 1
    assert snap["fk_edges"] == []  # ref to undefined table skipped, no crash


def test_dbml_snapshot_feeds_existing_ddl_export():
    ddl = snapshot_json_to_sql(parse_dbml(BASIC), target_dialect="postgresql")
    assert 'CREATE TABLE IF NOT EXISTS "public"."users"' in ddl
    assert 'CREATE TABLE IF NOT EXISTS "public"."posts"' in ddl
    assert "PRIMARY KEY" in ddl


def test_pathological_long_line_is_skipped_fast():
    import time

    hostile = 'Table t {\n  id int [pk]\n}\nRef: ' + '"a' * 100_000 + "\n"
    start = time.monotonic()
    snap = parse_dbml(hostile)
    assert time.monotonic() - start < 1.0  # no catastrophic backtracking
    assert len(snap["relations"]) == 1


def test_pathological_table_header_dots_are_rejected_fast():
    import time

    hostile = "Table ." + "." * 4000 + "\nTable users {\n  id int [pk]\n}\n"
    start = time.monotonic()
    snap = parse_dbml(hostile)
    assert time.monotonic() - start < 1.0
    assert {(r["schema_name"], r["relation_name"]) for r in snap["relations"]} == {
        ("public", "users")
    }
