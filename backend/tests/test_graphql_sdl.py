from __future__ import annotations

import re

from app.spec.graphql_sdl import generate_graphql_sdl

SNAP = {
    "relations": [
        {"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "member"},
        {"relation_oid": 2, "relation_kind": "r", "schema_name": "public", "relation_name": "order_item"},
        {"relation_oid": 3, "relation_kind": "v", "schema_name": "public", "relation_name": "v_report"},
    ],
    "columns": [
        {"relation_oid": 1, "column_name": "member_id", "column_position": 1, "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 1, "column_name": "email", "column_position": 2, "data_type": "text", "is_not_null": True},
        {"relation_oid": 1, "column_name": "score", "column_position": 3, "data_type": "numeric(5,2)", "is_not_null": False},
        {"relation_oid": 2, "column_name": "id", "column_position": 1, "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 2, "column_name": "member_id", "column_position": 2, "data_type": "bigint", "is_not_null": True},
    ],
    "pk_columns": [
        {"relation_oid": 1, "column_name": "member_id"},
        {"relation_oid": 2, "column_name": "id"},
    ],
    "fk_edges": [
        {"child_relation_oid": 2, "parent_relation_oid": 1,
         "child_column_name": "member_id", "parent_column_name": "member_id"},
    ],
}


def test_types_fields_nullability_and_pk_as_id():
    sdl = generate_graphql_sdl(SNAP)
    assert "type Member {" in sdl
    assert "type OrderItem {" in sdl
    assert "VReport" not in sdl  # views excluded
    assert "member_id: ID!" in sdl  # bigint PK -> ID!
    assert "email: String!" in sdl
    assert "score: Float" in sdl and "score: Float!" not in sdl


def test_fk_relations_both_directions_and_query_root():
    sdl = generate_graphql_sdl(SNAP)
    assert "member: Member" in sdl           # child -> parent object field
    assert "order_item: [OrderItem!]" in sdl  # parent -> children list
    assert "type Query {" in sdl


def test_hostile_identifiers_are_sanitized_to_valid_gql_names():
    snap = {
        "relations": [{"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "2fa-codes"}],
        "columns": [{"relation_oid": 1, "column_name": "user id!", "column_position": 1, "data_type": "text", "is_not_null": False}],
        "pk_columns": [], "fk_edges": [],
    }
    sdl = generate_graphql_sdl(snap)
    # every declared field/type name must be a valid GraphQL name
    for name in re.findall(r"^(?:type\s+(\w[\w]*)|\s{2}([\w]+):)", sdl, re.MULTILINE):
        for part in name:
            if part:
                assert re.fullmatch(r"[_A-Za-z][_0-9A-Za-z]*", part), part
    assert "# was: user id!" in sdl  # original kept in comment


def test_empty_snapshot():
    assert generate_graphql_sdl({}).startswith("# Generated")
    assert "type Query" not in generate_graphql_sdl({})
