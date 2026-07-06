from __future__ import annotations

import ast

from app.spec.orm_codegen import generate_prisma_schema, generate_sqlalchemy_models

SNAP = {
    "relations": [
        {"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "member", "relation_comment": "회원"},
        {"relation_oid": 2, "relation_kind": "r", "schema_name": "public", "relation_name": "orders", "relation_comment": None},
        {"relation_oid": 3, "relation_kind": "v", "schema_name": "public", "relation_name": "v_report"},
    ],
    "columns": [
        {"relation_oid": 1, "column_name": "member_id", "column_position": 1, "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 1, "column_name": "email", "column_position": 2, "data_type": "varchar(255)", "is_not_null": True},
        {"relation_oid": 1, "column_name": "joined_at", "column_position": 3, "data_type": "timestamp with time zone", "is_not_null": False},
        {"relation_oid": 2, "column_name": "order_id", "column_position": 1, "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 2, "column_name": "member_id", "column_position": 2, "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 2, "column_name": "total", "column_position": 3, "data_type": "numeric(10,2)", "is_not_null": False},
    ],
    "pk_columns": [
        {"relation_oid": 1, "column_name": "member_id"},
        {"relation_oid": 2, "column_name": "order_id"},
    ],
    "fk_edges": [
        {"fk_constraint_oid": 10, "fk_constraint_name": "fk_orders_member",
         "child_relation_oid": 2, "parent_relation_oid": 1,
         "child_column_name": "member_id", "parent_column_name": "member_id", "column_ordinal": 1},
    ],
}


def test_sqlalchemy_output_is_valid_python_with_expected_shapes():
    code = generate_sqlalchemy_models(SNAP)
    ast.parse(code)  # must always be syntactically valid Python
    assert "class Member(Base):" in code
    assert "class Orders(Base):" in code
    assert "class VReport" not in code  # views excluded
    assert "member_id: Mapped[int] = mapped_column(primary_key=True)" in code
    assert "joined_at: Mapped[dt.datetime | None] = mapped_column()" in code
    assert 'ForeignKey("member.member_id")' in code
    assert "total: Mapped[Decimal | None]" in code


def test_sqlalchemy_unknown_type_falls_back_with_comment():
    snap = {
        "relations": [{"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "t"}],
        "columns": [{"relation_oid": 1, "column_name": "shape", "column_position": 1, "data_type": "polygon", "is_not_null": False}],
        "pk_columns": [], "fk_edges": [],
    }
    code = generate_sqlalchemy_models(snap)
    ast.parse(code)
    assert "shape: Mapped[str | None] = mapped_column()  # type: polygon" in code


def test_prisma_models_relations_and_map():
    schema = generate_prisma_schema(SNAP)
    assert "model Member {" in schema and "model Orders {" in schema
    assert "member_id BigInt @id" in schema
    assert "member Member @relation(fields: [member_id], references: [member_id])" in schema
    assert "orderss Orders[]" in schema or "orders Orders[]" in schema  # reverse side exists
    assert '@@map("orders")' in schema
    assert "total Decimal?" in schema


def test_composite_pk_and_empty_snapshot():
    snap = {
        "relations": [{"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "m2m"}],
        "columns": [
            {"relation_oid": 1, "column_name": "a_id", "column_position": 1, "data_type": "bigint", "is_not_null": True},
            {"relation_oid": 1, "column_name": "b_id", "column_position": 2, "data_type": "bigint", "is_not_null": True},
        ],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "a_id"},
            {"relation_oid": 1, "column_name": "b_id"},
        ],
        "fk_edges": [],
    }
    schema = generate_prisma_schema(snap)
    assert "@@id([a_id, b_id])" in schema
    assert "@id\n" not in schema.replace("@@id", "")  # no single-column @id emitted
    ast.parse(generate_sqlalchemy_models({}))  # empty snapshot still valid


def test_typeorm_entities_decorators_and_relations():
    from app.spec.orm_codegen import generate_typeorm_entities

    code = generate_typeorm_entities(SNAP)
    assert "@Entity('member')" in code
    assert "export class Member {" in code
    assert "@PrimaryColumn()" in code
    assert "member_id!: number;" in code
    assert "joined_at?: Date | null;" in code
    assert "@ManyToOne(() => Member)" in code
    assert "@JoinColumn({ name: 'member_id' })" in code
    assert "@OneToMany(() => Orders" in code
    # balanced braces => structurally sound TS
    assert code.count("{") == code.count("}")
