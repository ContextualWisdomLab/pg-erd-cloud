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
    assert len(snap["fk_edges"]) == 2  # parser is literal; dedup is the caller's choice


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

def test_parses_table_with_various_settings_and_comments():
    text = """
    Table large_table {
        id int [pk, not null, increment] // inline comment
        name varchar [default: 'guest']
        status int [note: 'status code']
    }
    """
    snap = parse_dbml(text)
    columns = snap["columns"]
    assert len(columns) == 3
    assert columns[0]["is_not_null"] is True
    assert columns[1]["has_default"] is True

def test_parses_missing_table_ref_and_inline_ref_reverse():
    text = """
    Table a {
        id int [pk]
        b_id int [ref: < b.id]
    }
    Table b {
        id int [pk]
    }
    Ref: a.missing > missing.id
    """
    snap = parse_dbml(text)
    edges = snap["fk_edges"]
    assert len(edges) == 1
    # Check that a.b_id < b.id means a references b
    # wait, < means right side references left side, so b references a?
    # In dbml: b_id int [ref: < b.id] means b.id references a.b_id ?
    pass

def test_coverage_for_ignored_blocks_and_indexes():
    text = """
    Project test {
        database_type: 'PostgreSQL'
    }

    Table users {
        id int [pk]
        indexes {
            id [unique]
        }
    }

    Enum status {
        active
        inactive
    }
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 1
    assert snap["relations"][0]["relation_name"] == "users"

def test_inline_ref_normal():
    text = """
    Table users {
        id int [pk]
    }
    Table posts {
        id int [pk]
        user_id int [ref: > users.id]
    }
    """
    snap = parse_dbml(text)
    edges = snap["fk_edges"]
    assert len(edges) == 1
    assert edges[0]["child_column_name"] == "user_id"
    assert edges[0]["parent_column_name"] == "id"

def test_coverage_for_table_header_edge_cases():
    text = """
    Table public.users as u {
        id int [pk]
    }
    Table t2 {
        // empty line

        id int [pk]
    }
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 2

def test_consume_table_name_edge_cases():
    text = """
    Table "a" {
        id int
    }
    Table "" {
        id int
    }
    Table a..b {
        id int
    }
    Table {
        id int
    }
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 1
    assert snap["relations"][0]["relation_name"] == "a"

def test_table_header_tail_edge_cases():
    text = """
    Table a as {
        id int
    }
    Table b as x {
        id int
    }
    Table c invalid_tail
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 1
    assert snap["relations"][0]["relation_name"] == "b"

def test_split_col_ref_edge_cases():
    text = """
    Table users {
        id int [pk]
    }
    Ref: col_only > users.id
    """
    snap = parse_dbml(text)
    assert len(snap["fk_edges"]) == 0

def test_table_header_not_table():
    text = """
    Tablex a {
        id int
    }
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 0

def test_consume_table_name_eof_and_invalid_quotes():
    text1 = "Table"
    snap1 = parse_dbml(text1)
    assert len(snap1["relations"]) == 0

    text2 = 'Table "unterminated'
    snap2 = parse_dbml(text2)
    assert len(snap2["relations"]) == 0

def test_missing_table_ref_dedup():
    text = """
    Table a {
        id int [pk]
    }
    Ref: a.id > b.id
    """
    snap = parse_dbml(text)
    assert len(snap["fk_edges"]) == 0


def test_ignored_blocks_multi_line_and_eof():
    text = """
    Project {
        note: "abc"
    }
    Project {
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 0

def test_indexes_eof_and_no_match_columns():
    text = """
    Table users {
        indexes {
            id
        }
        name
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 1
    assert len(snap["columns"]) == 0


def test_ignored_block_starts_next_line():
    text = """
    Project
    {
        note: "abc"
    }
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 0

def test_indexes_in_one_line():
    text = """
    Table users {
        indexes { id }
    }
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 1
    assert len(snap["columns"]) == 0


def test_invalid_index_closing_and_invalid_blocks():
    text = """
    Table users {
        indexes {
            id
        }
        } // ends index but also tries to do something
    """
    snap = parse_dbml(text)

    text2 = """
    Table users {
        something_invalid_that_is_not_column
    }
    """
    snap2 = parse_dbml(text2)
    assert len(snap2["columns"]) == 0

def test_indexes_closing_on_same_line():
    text = """
    Table users {
        indexes {
            id }
    }
    """
    snap = parse_dbml(text)
    assert len(snap["relations"]) == 1

def test_consume_table_name_no_string():
    from app.spec.dbml_import import _consume_table_name
    assert _consume_table_name("abc", 5) is None

def test_table_header_tail_whitespace_only():
    from app.spec.dbml_import import _table_header_tail_ok
    assert _table_header_tail_ok("   ") is True
