from __future__ import annotations

from app.sanitize import sanitize_for_storage, strip_nul


def test_sanitize_removes_nul() -> None:
    obj = {"a": "x\x00y", "b": ["\x00", "ok"], "c\x00": "v"}
    out = sanitize_for_storage(obj)
    assert out == {"a": "xy", "b": ["", "ok"], "c": "v"}

def test_strip_nul() -> None:
    # Test typical null byte removals
    assert strip_nul("hello\x00world") == "helloworld"
    assert strip_nul("\x00") == ""
    assert strip_nul("no nulls here") == "no nulls here"

    # Test non-string behavior (if type checks are invoked/ignored appropriately by caller)
    assert strip_nul(None) is None  # type: ignore
    assert strip_nul(123) == 123    # type: ignore
    assert strip_nul(["\x00"]) == ["\x00"]  # type: ignore
