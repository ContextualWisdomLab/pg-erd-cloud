from __future__ import annotations

import base64
from collections.abc import Mapping


def strip_nul(value: str) -> str:
    """Remove NUL (0x00) characters from a string."""

    # PostgreSQL text/json rejects NUL(0x00). Remove it.
    return value.replace("\x00", "")


def sanitize_for_storage(obj: object) -> object:
    """Recursively sanitize strings for DB storage.

    - Removes NUL chars from *all* strings.
    - Converts bytes/memoryview to safe text (best-effort UTF-8; fallback base64).
    """

    if obj is None:
        return obj
    if isinstance(obj, str):
        return strip_nul(obj)
    if isinstance(obj, memoryview):
        obj = obj.tobytes()
    if isinstance(obj, (bytes, bytearray)):
        try:
            return strip_nul(bytes(obj).decode("utf-8"))
        except Exception:  # noqa: BLE001
            return base64.b64encode(bytes(obj)).decode("ascii")
    if isinstance(obj, list):
        return [sanitize_for_storage(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(sanitize_for_storage(v) for v in obj)
    if isinstance(obj, Mapping):
        return {
            strip_nul(str(k)): sanitize_for_storage(v) for k, v in obj.items()
        }
    return obj
