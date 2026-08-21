from __future__ import annotations

from app.spec.wide_tables import detect_wide_tables


def _snap(table_widths, kinds=None):
    """table_widths: {name: n_columns}"""
    kinds = kinds or {}
    relations, columns = [], []
    for oid, (t, n) in enumerate(table_widths.items(), start=1):
        relations.append({"relation_oid": oid, "relation_kind": kinds.get(t, "r"), "schema_name": "public", "relation_name": t})
        for i in range(n):
            columns.append({"relation_oid": oid, "column_name": f"c{i}"})
    return {"relations": relations, "columns": columns}


def test_flags_wide_and_god_tables_by_threshold():
    report = detect_wide_tables(_snap({"slim": 5, "wide": 30, "god": 60}))
    byt = {i["table"]: i["severity"] for i in report["items"]}
    assert "public.slim" not in byt
    assert byt["public.wide"] == "info"     # 30 > 25
    assert byt["public.god"] == "warning"   # 60 > 40


def test_sorted_widest_first_and_summary():
    report = detect_wide_tables(_snap({"a": 30, "b": 50, "c": 45}))
    assert [i["columns"] for i in report["items"]] == [50, 45, 30]
    assert report["summary"]["warning"] == 2  # b, c
    assert report["summary"]["info"] == 1     # a


def test_custom_thresholds():
    report = detect_wide_tables(_snap({"t": 12}), warn_threshold=20, info_threshold=10)
    assert report["items"][0]["severity"] == "info"  # 12 > 10
    assert report["summary"]["info_threshold"] == 10


def test_views_excluded_and_empty():
    report = detect_wide_tables(_snap({"v_big": 80}, kinds={"v_big": "v"}))
    assert report["items"] == []
    assert detect_wide_tables({})["summary"]["total"] == 0
