from __future__ import annotations

from app.sanitize import sanitize_for_storage, strip_nul


def test_sanitize_removes_nul() -> None:
    obj = {"a": "x\x00y", "b": ["\x00", "ok"], "c\x00": "v"}
    out = sanitize_for_storage(obj)
    assert out == {"a": "xy", "b": ["", "ok"], "c": "v"}


def test_strip_nul_removes_nul_characters_from_strings() -> None:
    assert strip_nul("hello\x00world") == "helloworld"
    assert strip_nul("\x00") == ""
    assert strip_nul("no nulls here") == "no nulls here"
