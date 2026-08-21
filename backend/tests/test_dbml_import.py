from __future__ import annotations

import pytest

from app.ddl.export import snapshot_json_to_sql
from app.spec.dbml_import import DbmlIdentifierError, parse_dbml

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


def test_pathological_long_line_is_rejected_fast():
    import time

    hostile = 'Table t {\n  id int [pk]\n}\nRef: ' + '"a' * 100_000 + "\n"
    start = time.monotonic()
    with pytest.raises(DbmlIdentifierError):
        parse_dbml(hostile)
    assert time.monotonic() - start < 1.0  # no catastrophic backtracking


def test_pathological_table_header_dots_are_rejected_fast():
    import time

    hostile = "Table ." + "." * 4000 + "\nTable users {\n  id int [pk]\n}\n"
    start = time.monotonic()
    snap = parse_dbml(hostile)
    assert time.monotonic() - start < 1.0
    assert {(r["schema_name"], r["relation_name"]) for r in snap["relations"]} == {
        ("public", "users")
    }


def test_quoted_identifiers_round_trip_through_postgresql_ddl() -> None:
    """Quoted DBML names must decode once and re-escape at the DDL sink."""
    text = '''
Table "odd""schema"."select; -- audit" {
  "quote""column" integer [pk]
}
'''

    snapshot = parse_dbml(text)
    ddl = snapshot_json_to_sql(snapshot, target_dialect="postgresql")

    assert snapshot["relations"][0]["schema_name"] == 'odd"schema'
    assert snapshot["relations"][0]["relation_name"] == "select; -- audit"
    assert snapshot["columns"][0]["column_name"] == 'quote"column'
    assert 'CREATE SCHEMA IF NOT EXISTS "odd""schema";' in ddl
    assert (
        'CREATE TABLE IF NOT EXISTS "odd""schema"."select; -- audit" (' in ddl
    )
    assert '"quote""column" integer NOT NULL' in ddl
    assert 'CONSTRAINT "pk_select; -- audit" PRIMARY KEY ("quote""column")' in ddl


def test_unicode_line_separator_inside_quoted_identifier_is_data() -> None:
    """Only LF separates DBML records; Unicode separators remain identifier data."""
    identifier = "order\x85items"

    snapshot = parse_dbml(f'Table "{identifier}" {{\n  id integer\n}}')

    assert snapshot["relations"][0]["relation_name"] == identifier


@pytest.mark.parametrize(
    "dbml",
    [
        'Table "unterminated {\n  id integer\n}',
        'Table public.orders.extra {\n  id integer\n}',
        'Table "nul\x00name" {\n  id integer\n}',
        f'Table "{"é" * 32}" {{\n  id integer\n}}',
        'Table users {\n  "unterminated integer\n}',
        'Table users {\n  "nul\x00column" integer\n}',
        'Ref: catalog.public.users.id > public.accounts.id',
        'Ref: "unterminated > public.accounts.id',
    ],
)
def test_invalid_or_ambiguous_dbml_identifiers_fail_closed(dbml: str) -> None:
    """Malformed, ambiguous, NUL, and overlong names must not degrade to omission."""
    with pytest.raises(DbmlIdentifierError):
        parse_dbml(dbml)


def test_comment_markers_and_dots_inside_quoted_names_are_data() -> None:
    """DBML comments and path separators apply only outside quoted identifiers."""
    snapshot = parse_dbml(
        '''
Table "odd.schema"."orders//archive" {
  "value.part//raw" integer [pk]
}
'''
    )

    relation = snapshot["relations"][0]
    assert relation["schema_name"] == "odd.schema"
    assert relation["relation_name"] == "orders//archive"
    assert snapshot["columns"][0]["column_name"] == "value.part//raw"


def test_generated_constraint_names_fit_postgresql_identifier_limit() -> None:
    """Derived names must never rely on PostgreSQL's lossy identifier truncation."""
    relation_name = "r" * 61
    snapshot = parse_dbml(f"Table {relation_name} {{\n  id integer [pk]\n}}")

    constraint_name = snapshot["constraints"][0]["constraint_name"]

    assert len(constraint_name.encode("utf-8")) <= 63
    assert constraint_name.startswith("pk_")


def test_parser_rejects_input_above_authenticated_route_limit() -> None:
    """Direct parser callers inherit the route's total-input resource bound."""
    with pytest.raises(DbmlIdentifierError):
        parse_dbml("\n".join("x" * 3_000 for _ in range(200)))


def test_parser_rejects_more_than_ten_thousand_lines() -> None:
    """Line iteration is bounded even when each attacker-controlled line is tiny."""
    with pytest.raises(DbmlIdentifierError):
        parse_dbml("\n" * 10_001)


def test_column_positions_scale_and_reset_per_relation() -> None:
    """Column ordinals stay linear and restart independently for every relation."""
    first_columns = "\n".join(
        f"  column_{index} integer" for index in range(1_000)
    )
    text = f"""
Table wide_relation {{
{first_columns}
}}
Table second_relation {{
  first_column integer
  second_column integer
}}
"""

    snapshot = parse_dbml(text)
    relation_oids = {
        relation["relation_name"]: relation["relation_oid"]
        for relation in snapshot["relations"]
    }
    wide_positions = [
        column["column_position"]
        for column in snapshot["columns"]
        if column["relation_oid"] == relation_oids["wide_relation"]
    ]
    second_positions = [
        column["column_position"]
        for column in snapshot["columns"]
        if column["relation_oid"] == relation_oids["second_relation"]
    ]

    assert wide_positions == list(range(1, 1_001))
    assert second_positions == [1, 2]
