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
    text = """
Table auth.accounts {
  account_id bigint [pk]
}
Table "Order Items" {
  id bigint [pk]
  account_id bigint
}
Ref: auth.accounts.account_id < "Order Items".account_id
"""
    snap = parse_dbml(text)
    assert ("auth", "accounts") in {
        (r["schema_name"], r["relation_name"]) for r in snap["relations"]
    }
    edge = snap["fk_edges"][0]
    # '<' means the right side references the left
    child = next(
        r for r in snap["relations"] if r["relation_oid"] == edge["child_relation_oid"]
    )
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


def test_preserves_column_defaults_for_snapshot_and_ddl_export():
    snap = parse_dbml(
        """
Table public.accounts {
  id integer [pk]
  email varchar [unique]
  status varchar [default: 'active, pending']
  full_name varchar [default: `coalesce(first_name, last_name)`]
  created_at timestamptz [default: now()]
}
"""
    )

    columns = {column["column_name"]: column for column in snap["columns"]}
    assert columns["status"]["has_default"] is True
    assert columns["status"]["default_expr"] == "'active, pending'"
    assert columns["full_name"]["default_expr"] == "`coalesce(first_name, last_name)`"
    assert columns["created_at"]["default_expr"] == "now()"
    unique_email = next(
        index for index in snap["indexes"] if index["is_unique"] and '"email"' in index["index_def"]
    )
    assert unique_email["index_def"].startswith('CREATE UNIQUE INDEX')
    ddl = snapshot_json_to_sql(snap, target_dialect="postgresql")
    assert "DEFAULT 'active, pending'" in ddl
    assert "DEFAULT now()" in ddl


def test_parses_simple_index_blocks_and_preserves_ddl_evidence():
    snap = parse_dbml(
        """
Table public.lineage {
  id integer [pk]
  workspace_id varchar
  fingerprint varchar
  created_at timestamptz
  indexes {
    (workspace_id, fingerprint) [unique]
    (created_at) [name: 'ix_lineage_created', type: hash]
    (missing_column) [unique]
  }
}
"""
    )
    assert len(snap["indexes"]) == 2
    unique, named = snap["indexes"]
    assert unique["is_unique"] is True
    assert unique["access_method"] == "btree"
    assert '"workspace_id", "fingerprint"' in unique["index_def"]
    assert named["index_name"] == "ix_lineage_created"
    assert named["access_method"] == "hash"
    ddl = snapshot_json_to_sql(snap, target_dialect="postgresql")
    assert (
        'CREATE UNIQUE INDEX CONCURRENTLY "ix_lineage_workspace_id_fingerprint_1"'
        in ddl
    )
    assert 'CREATE INDEX CONCURRENTLY "ix_lineage_created"' in ddl


def test_index_tuple_closes_only_outside_quoted_identifier():
    snap = parse_dbml(
        '''
Table public.metrics {
  "sales)region" varchar
  indexes {
    ("sales)region") [unique]
  }
}
'''
    )

    assert len(snap["indexes"]) == 1
    assert '"sales)region"' in snap["indexes"][0]["index_def"]


def test_column_after_indexes_block_remains_in_current_table():
    snap = parse_dbml(
        """
Table public.events {
  id integer
  indexes {
    (id)
  }
  created_at timestamptz
}
"""
    )

    assert {column["column_name"] for column in snap["columns"]} == {
        "id",
        "created_at",
    }


def test_index_names_are_unique_in_schema_and_do_not_collide_with_relations():
    snap = parse_dbml(
        """
Table public.shared_name {
  id integer
  indexes {
    (id) [name: 'shared_name']
  }
}
Table public.second {
  id integer
  indexes {
    (id) [name: 'shared_name']
  }
}
"""
    )

    names = [index["index_name"] for index in snap["indexes"]]
    assert len(names) == len(set(names)) == 2
    assert "shared_name" not in names


def test_primary_index_becomes_constraint_without_duplicate_index():
    snap = parse_dbml(
        """
Table public.accounts {
  tenant_id integer
  account_id integer
  indexes {
    (tenant_id, account_id) [pk]
  }
}
"""
    )

    assert snap["indexes"] == []
    assert [column["column_name"] for column in snap["pk_columns"]] == [
        "tenant_id",
        "account_id",
    ]
    ddl = snapshot_json_to_sql(snap, target_dialect="postgresql")
    assert 'PRIMARY KEY ("tenant_id", "account_id")' in ddl
    assert "CREATE UNIQUE INDEX" not in ddl


def test_pathological_long_line_is_skipped_fast():
    import time

    hostile = "Table t {\n  id int [pk]\n}\nRef: " + '"a' * 100_000 + "\n"
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
