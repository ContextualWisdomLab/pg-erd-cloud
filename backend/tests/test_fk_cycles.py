from __future__ import annotations

from app.spec.fk_cycles import detect_fk_cycles


def _snap(edges, names=None):
    names = names or sorted({e[0] for e in edges} | {e[1] for e in edges})
    oid = {n: i + 1 for i, n in enumerate(names)}
    return {
        "relations": [{"relation_oid": oid[n], "schema_name": "public", "relation_name": n} for n in names],
        "fk_edges": [
            {"child_relation_oid": oid[c], "parent_relation_oid": oid[p], "child_column_name": "x", "parent_column_name": "y"}
            for c, p in edges
        ],
    }


def test_detects_multi_table_cycle():
    # a -> b -> c -> a
    report = detect_fk_cycles(_snap([("a", "b"), ("b", "c"), ("c", "a")]))
    assert report["summary"]["circular_dependencies"] == 1
    cyc = next(i for i in report["items"] if i["category"] == "circular_dependency")
    assert set(cyc["tables"]) == {"public.a", "public.b", "public.c"}
    assert cyc["severity"] == "warning"


def test_two_node_cycle():
    report = detect_fk_cycles(_snap([("a", "b"), ("b", "a")]))
    assert report["summary"]["circular_dependencies"] == 1


def test_self_reference_is_info_not_a_cycle():
    report = detect_fk_cycles(_snap([("employee", "employee")], names=["employee"]))
    assert report["summary"]["circular_dependencies"] == 0
    assert report["summary"]["self_references"] == 1
    assert report["items"][0]["severity"] == "info"


def test_acyclic_graph_has_no_findings():
    report = detect_fk_cycles(_snap([("orders", "member"), ("order_item", "orders")]))
    assert report["items"] == []


def test_two_independent_cycles_and_deep_chain_no_recursion_error():
    edges = [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")]
    # long acyclic chain to exercise the iterative SCC
    chain = [f"n{i}" for i in range(1500)]
    edges += [(chain[i], chain[i + 1]) for i in range(len(chain) - 1)]
    report = detect_fk_cycles(_snap(edges))
    assert report["summary"]["circular_dependencies"] == 2
