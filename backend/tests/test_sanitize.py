from __future__ import annotations

from app.sanitize import sanitize_for_storage


def test_sanitize_removes_nul() -> None:
    obj = {"a": "x\x00y", "b": ["\x00", "ok"], "c\x00": "v"}
    out = sanitize_for_storage(obj)
    assert out == {"a": "xy", "b": ["", "ok"], "c": "v"}
