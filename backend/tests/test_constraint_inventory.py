from __future__ import annotations

from app.spec.constraint_inventory import build_constraint_inventory


def _con(ctype, name, table="orders", ftable=None, on_delete=None, check_expr=None):
    return {
        "constraint_type": ctype,
        "constraint_name": name,
        "schema_name": "public",
        "relation_name": table,
        "foreign_schema_name": "public" if ftable else None,
        "foreign_relation_name": ftable,
        "fk_on_delete": on_delete,
        "check_expr": check_expr,
        "constraint_def": f"DEF {name}",
    }


def test_inventories_check_constraints_with_expressions():
    snap = {"constraints": [
        _con("c", "chk_qty_positive", check_expr="(quantity > 0)"),
        _con("c", "chk_status", table="member", check_expr="(status IN ('active','banned'))"),
        _con("p", "pk_orders"),
    ]}
    inv = build_constraint_inventory(snap)
    assert inv["summary"]["check_rules"] == 2
    assert inv["check_rules"][0]["table"] == "public.member"  # sorted by table
    assert inv["check_rules"][1]["expression"] == "(quantity > 0)"


def test_flags_cascade_delete_as_warning():
    snap = {"constraints": [
        _con("f", "fk_item_order", table="order_item", ftable="orders", on_delete="c"),
    ]}
    inv = build_constraint_inventory(snap)
    assert inv["summary"]["cascade_deletes"] == 1
    item = inv["delete_actions"][0]
    assert item["severity"] == "warning"
    assert "public.orders" in item["detail"] and "public.order_item" in item["detail"]


def test_set_null_is_info_and_spelled_out_codes_work():
    snap = {"constraints": [
        _con("f", "fk_a", table="a", ftable="b", on_delete="set null"),
        _con("f", "fk_c", table="c", ftable="d", on_delete="CASCADE"),
        _con("f", "fk_plain", table="e", ftable="f", on_delete="a"),  # no action
    ]}
    inv = build_constraint_inventory(snap)
    assert inv["summary"]["set_null_deletes"] == 1
    assert inv["summary"]["cascade_deletes"] == 1
    # warnings sort before infos
    assert [i["severity"] for i in inv["delete_actions"]] == ["warning", "info"]


def test_check_without_expr_falls_back_to_def_and_empty():
    snap = {"constraints": [_con("c", "chk_x", check_expr=None)]}
    inv = build_constraint_inventory(snap)
    assert inv["check_rules"][0]["expression"] == "DEF chk_x"
    assert build_constraint_inventory({})["summary"]["check_rules"] == 0
