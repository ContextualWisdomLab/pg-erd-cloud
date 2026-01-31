from __future__ import annotations

from collections.abc import Mapping


def strip_nul(value: str) -> str:
    # PostgreSQL text/json rejects NUL(0x00). Remove it.
    return value.replace("\x00", "")


def sanitize_for_storage(obj: object) -> object:
    """Recursively sanitize strings for DB storage.

    - Removes NUL chars from *all* strings.
    - Leaves bytes/bytearray unchanged (binary data should not be stored in text).
    """

    if obj is None:
        return obj
    if isinstance(obj, str):
        return strip_nul(obj)
    if isinstance(obj, (bytes, bytearray)):
        return obj
    if isinstance(obj, list):
        return [sanitize_for_storage(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(sanitize_for_storage(v) for v in obj)
    if isinstance(obj, Mapping):
        return {strip_nul(str(k)): sanitize_for_storage(v) for k, v in obj.items()}
    return obj
