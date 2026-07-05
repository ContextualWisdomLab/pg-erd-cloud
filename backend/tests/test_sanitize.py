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


def test_sanitize_converts_memoryview_and_bytes_to_text() -> None:
    import base64

    assert sanitize_for_storage(memoryview(b"hi")) == "hi"
    assert sanitize_for_storage(b"ok\x00") == "ok"  # utf-8 decode + NUL strip
    assert sanitize_for_storage(bytearray(b"a")) == "a"
    raw = b"\xff\xfe"  # invalid utf-8 -> base64 fallback
    assert sanitize_for_storage(raw) == base64.b64encode(raw).decode("ascii")


def test_sanitize_preserves_tuples_and_passes_through_scalars() -> None:
    assert sanitize_for_storage(("a\x00", ["b\x00"])) == ("a", ["b"])
    assert sanitize_for_storage(5) == 5
    assert sanitize_for_storage(None) is None
