from __future__ import annotations

from app.spec.relationship_inference import infer_relationships


def _snapshot(*, declare_fk=False, member_plural=False, id_type="bigint"):
    member_name = "members" if member_plural else "member"
    return {
        "relations": [
            {"relation_oid": 1, "schema_name": "public", "relation_name": member_name},
            {"relation_oid": 2, "schema_name": "public", "relation_name": "orders"},
        ],
        "columns": [
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint"},
            {"relation_oid": 1, "column_name": "email", "data_type": "text"},
            {"relation_oid": 2, "column_name": "order_id", "data_type": "bigint"},
            {"relation_oid": 2, "column_name": "member_id", "data_type": id_type},
        ],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "member_id"},
            {"relation_oid": 2, "column_name": "order_id"},
        ],
        "fk_edges": (
            [
                {
                    "child_relation_oid": 2,
                    "parent_relation_oid": 1,
                    "child_column_name": "member_id",
                    "parent_column_name": "member_id",
                }
            ]
            if declare_fk
            else []
        ),
    }


def test_infers_member_id_to_member_with_high_confidence():
    rels = infer_relationships(_snapshot())
    assert len(rels) == 1
    r = rels[0]
    assert (r["child_table"], r["child_column"]) == ("orders", "member_id")
    assert (r["parent_table"], r["parent_column"]) == ("member", "member_id")
    assert r["confidence"] == "high"


def test_skips_already_declared_foreign_keys():
    assert infer_relationships(_snapshot(declare_fk=True)) == []


def test_medium_confidence_when_types_differ():
    rels = infer_relationships(_snapshot(id_type="integer"))
    assert len(rels) == 1
    assert rels[0]["confidence"] == "medium"
    assert "type differs" in rels[0]["reason"]


def test_matches_plural_table_name():
    rels = infer_relationships(_snapshot(member_plural=True))
    assert len(rels) == 1
    assert rels[0]["parent_table"] == "members"


def test_no_inference_without_a_matching_table_or_pk():
    snap = {
        "relations": [
            {"relation_oid": 2, "schema_name": "public", "relation_name": "orders"}
        ],
        "columns": [
            # references a "member" table that does not exist
            {"relation_oid": 2, "column_name": "member_id", "data_type": "bigint"},
        ],
        "pk_columns": [],
        "fk_edges": [],
    }
    assert infer_relationships(snap) == []
    assert infer_relationships({}) == []


def test_only_infers_within_the_same_schema():
    snap = {
        "relations": [
            {"relation_oid": 1, "schema_name": "core", "relation_name": "member"},
            {"relation_oid": 2, "schema_name": "sales", "relation_name": "orders"},
        ],
        "columns": [
            {"relation_oid": 1, "column_name": "member_id", "data_type": "bigint"},
            {"relation_oid": 2, "column_name": "member_id", "data_type": "bigint"},
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "member_id"}],
        "fk_edges": [],
    }
    # orders is in 'sales', member is in 'core' -> no cross-schema guess
    assert infer_relationships(snap) == []
