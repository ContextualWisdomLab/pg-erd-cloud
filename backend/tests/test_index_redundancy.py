from __future__ import annotations

from app.spec.index_redundancy import detect_index_redundancy


def _snap(index_defs, unique=None):
    """index_defs: {index_name: 'col1, col2'} on one table 'orders'."""
    unique = unique or set()
    return {
        "relations": [{"relation_oid": 1, "schema_name": "public", "relation_name": "orders"}],
        "indexes": [
            {
                "relation_oid": 1,
                "index_name": name,
                "is_unique": name in unique,
                "index_def": f"CREATE INDEX {name} ON public.orders USING btree ({cols})",
            }
            for name, cols in index_defs.items()
        ],
    }


def _cats(report):
    return {(i["category"], i["index"]) for i in report["items"]}


def test_detects_exact_duplicate():
    report = detect_index_redundancy(_snap({"ix_a": "member_id", "ix_b": "member_id"}))
    assert report["summary"]["duplicates"] == 1
    dup = report["items"][0]
    assert dup["severity"] == "warning" and dup["columns"] == ["member_id"]


def test_duplicate_keeps_the_unique_one():
    report = detect_index_redundancy(
        _snap({"uq_a": "email", "ix_b": "email"}, unique={"uq_a"})
    )
    dup = report["items"][0]
    assert dup["index"] == "ix_b" and dup["kept"] == "uq_a"


def test_detects_prefix_redundancy_but_not_unique_prefix():
    # ix_short(member_id) is a prefix of ix_long(member_id, created_at)
    report = detect_index_redundancy(
        _snap({"ix_short": "member_id", "ix_long": "member_id, created_at"})
    )
    assert ("prefix_redundant_index", "ix_short") in _cats(report)

    # but a UNIQUE index is a constraint — never suggested for dropping
    report2 = detect_index_redundancy(
        _snap({"uq_short": "member_id", "ix_long": "member_id, created_at"}, unique={"uq_short"})
    )
    assert report2["items"] == []


def test_different_columns_and_unparseable_defs_are_skipped():
    report = detect_index_redundancy(_snap({"ix_a": "member_id", "ix_b": "created_at"}))
    assert report["items"] == []
    # expression + partial indexes are skipped, not guessed
    snap = _snap({"ix_a": "member_id"})
    snap["indexes"].append({"relation_oid": 1, "index_name": "ix_expr",
                            "index_def": "CREATE INDEX ix_expr ON public.orders (lower(email))"})
    snap["indexes"].append({"relation_oid": 1, "index_name": "ix_part",
                            "index_def": "CREATE INDEX ix_part ON public.orders (member_id) WHERE deleted_at IS NULL"})
    assert detect_index_redundancy(snap)["items"] == []
    assert detect_index_redundancy({})["summary"]["total"] == 0
