from __future__ import annotations

import random
import uuid

import pytest
from fastapi import HTTPException

from app.api.dbml import convert_dbml
from app.auth import CurrentUser
from app.ddl.export import snapshot_json_to_sql
from app.pg_introspect.forward_ddl import _split_statements
from app.schemas import DbmlConvertIn
from app.spec.dbml_import import DbmlParseError, parse_dbml

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


def test_standalone_reference_rejects_trailing_tokens():
    dbml = """
Table users {
  id integer [pk]
}
Table posts {
  user_id integer
}
Ref: posts.user_id > users.id trailing
"""

    with pytest.raises(DbmlParseError, match="malformed reference identifier"):
        parse_dbml(dbml)


def test_inline_reference_requires_a_settings_delimiter_after_the_path():
    malformed = """
Table users {
  id integer [pk]
}
Table posts {
  user_id integer [ref: > users.id trailing]
}
"""
    valid_with_following_setting = malformed.replace(
        "users.id trailing", "users.id, not null"
    )

    assert parse_dbml(malformed)["fk_edges"] == []
    assert len(parse_dbml(valid_with_following_setting)["fk_edges"]) == 1


def test_named_block_reference_preserves_anchored_delimiters():
    dbml = """
Table users {
  id integer [pk]
}
Table posts {
  user_id integer
}
Ref user_posts { posts.user_id > users.id }
"""

    edge = parse_dbml(dbml)["fk_edges"][0]

    assert edge["child_column_name"] == "user_id"
    assert edge["parent_column_name"] == "id"


def test_named_short_reference_accepts_a_colon():
    dbml = """
Table users {
  id integer [pk]
}
Table posts {
  user_id integer
}
Ref user_posts: posts.user_id > users.id
"""

    edge = parse_dbml(dbml)["fk_edges"][0]

    assert edge["child_column_name"] == "user_id"
    assert edge["parent_column_name"] == "id"


def test_double_quote_inside_single_quoted_setting_does_not_end_comment_scan():
    dbml = """
Table users {
  id integer [pk, note: 'diameter 5\" pipe // remains text']
}
"""

    snapshot = parse_dbml(dbml)

    assert snapshot["relations"][0]["relation_name"] == "users"
    assert snapshot["columns"][0]["column_name"] == "id"


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


def test_quoted_identifiers_round_trip_through_postgresql_ddl_as_one_statement():
    dbml = '''
Table "Odd ""Table;--//""" {
  "select" text [pk]
  "Snow ☃" text
}
'''

    snapshot = parse_dbml(dbml)
    ddl = snapshot_json_to_sql(snapshot, target_dialect="postgresql")

    relation = snapshot["relations"][0]
    assert relation["relation_name"] == 'Odd "Table;--//"'
    assert {column["column_name"] for column in snapshot["columns"]} == {
        "select",
        "Snow ☃",
    }
    assert '"public"."Odd ""Table;--//"""' in ddl
    assert 'PRIMARY KEY ("select")' in ddl
    assert ddl.count("CREATE TABLE") == 1
    assert len(_split_statements(ddl)) == 2


@pytest.mark.parametrize(
    "dbml",
    [
        'Table "unterminated {\n  id int\n}',
        'Table public..orders {\n  id int\n}',
        'Table one.two.three {\n  id int\n}',
        'Table "" {\n  id int\n}',
        'Table "bad\x00name" {\n  id int\n}',
        f'Table "{"é" * 32}" {{\n  id int\n}}',
        'Table safe {\n  "unterminated int\n}',
        'Table safe {\n  "bad\x00column" int\n}',
    ],
)
def test_malformed_or_unrepresentable_identifiers_fail_closed(dbml: str):
    with pytest.raises(DbmlParseError):
        parse_dbml(dbml)


@pytest.mark.parametrize(
    "identifier",
    [
        "ordinary_name",
        "select",
        "white space",
        "semi;colon",
        "comment--marker",
        "slash//marker",
        'embedded"quote',
        "주문 내역",
        "é" * 31 + "a",
    ],
)
def test_identifier_parse_render_round_trip(identifier: str):
    encoded = identifier.replace('"', '""')
    snapshot = parse_dbml(f'Table "{encoded}" {{\n  id int\n}}')
    ddl = snapshot_json_to_sql(snapshot)

    assert snapshot["relations"][0]["relation_name"] == identifier
    assert f'"{encoded}"' in ddl


def test_identifier_parse_render_property_fuzz_is_lossless():
    rng = random.Random(747)
    alphabet = (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ "
        ".,;:-/\\()[]{}!@#$%^&*+='\""
        "注文☃é"
    )

    for _ in range(250):
        identifier = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 20)))
        if len(identifier.encode("utf-8")) > 63:
            continue
        encoded = identifier.replace('"', '""')

        snapshot = parse_dbml(f'Table "{encoded}" {{\n  id int\n}}')
        ddl = snapshot_json_to_sql(snapshot)

        assert snapshot["relations"][0]["relation_name"] == identifier
        assert f'"{encoded}"' in ddl


def test_quoted_foreign_key_identifiers_use_the_same_renderer():
    dbml = '''
Table "parent"";--" {
  "id""value" bigint [pk]
}
Table "child" {
  "parent""id" bigint
}
Ref: "child"."parent""id" > "parent"";--"."id""value"
'''

    ddl = snapshot_json_to_sql(parse_dbml(dbml))

    assert 'REFERENCES "public"."parent"";--" ("id""value")' in ddl
    assert len(_split_statements(ddl)) == 4  # schema, two tables, one FK


@pytest.mark.asyncio
async def test_convert_api_reports_malformed_identifier_without_partial_output():
    with pytest.raises(HTTPException) as exc_info:
        await convert_dbml(
            DbmlConvertIn(dbml='Table "unterminated {\n id int\n}'),
            CurrentUser(uuid.uuid4(), "subject", "Test user"),
        )

    assert exc_info.value.status_code == 422
    assert "unterminated quoted identifier" in exc_info.value.detail


@pytest.mark.asyncio
async def test_pathological_long_line_fails_closed_fast():
    import time

    hostile = 'Table t {\n  id int [pk]\n}\nRef: ' + '"a' * 100_000 + "\n"
    start = time.monotonic()
    with pytest.raises(DbmlParseError, match="DBML line exceeds 4096 characters"):
        parse_dbml(hostile)
    assert time.monotonic() - start < 1.0  # no catastrophic backtracking

    with pytest.raises(HTTPException) as exc_info:
        await convert_dbml(
            DbmlConvertIn(dbml=hostile),
            CurrentUser(uuid.uuid4(), "subject", "Test user"),
        )

    assert exc_info.value.status_code == 422
    assert "DBML line exceeds 4096 characters" in exc_info.value.detail


def test_pathological_table_header_dots_are_rejected_fast():
    import time

    hostile = "Table ." + "." * 4000 + "\nTable users {\n  id int [pk]\n}\n"
    start = time.monotonic()
    with pytest.raises(DbmlParseError):
        parse_dbml(hostile)
    assert time.monotonic() - start < 1.0
