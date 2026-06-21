from __future__ import annotations

import base64
from collections.abc import Mapping


def strip_nul(value: str) -> str:
    """Remove NUL (0x00) characters from a string."""
    if not isinstance(value, str):
        return value

    # PostgreSQL text/json rejects NUL(0x00). Remove it.
    return value.replace("\x00", "")


MAX_RECURSION_DEPTH = 10
MAX_INPUT_SIZE = 10_000  # 10KB

def sanitize_for_storage(obj: object, depth: int = 0) -> object:
    """Recursively sanitize strings for DB storage.

    - Removes NUL chars from *all* strings.
    - Converts bytes/memoryview to safe text (best-effort UTF-8; fallback base64).
    """

    if depth > MAX_RECURSION_DEPTH:
        raise ValueError("Maximum recursion depth exceeded")

    if obj is None:
        return obj

    # Size check for strings/bytes
    if isinstance(obj, (str, bytes, bytearray, memoryview)) and len(obj) > MAX_INPUT_SIZE:
        raise ValueError("Input size exceeds maximum allowed")

    if isinstance(obj, str):
        # Remove path traversal sequences and absolute paths
        import os
        import posixpath
        import ntpath

        # Block absolute paths or relative traversals more aggressively
        if os.path.isabs(obj) or posixpath.isabs(obj) or ntpath.isabs(obj):
            raise ValueError("Absolute paths are not allowed")

        clean = obj.replace("../", "").replace("..\\", "")
        return strip_nul(clean)

    if isinstance(obj, memoryview):
        obj = obj.tobytes()

    if isinstance(obj, (bytes, bytearray)):
        try:
            return strip_nul(bytes(obj).decode("utf-8"))
        except Exception:  # noqa: BLE001
            # Mark base64 content with warning
            return "[BASE64-WARNING]" + base64.b64encode(bytes(obj)).decode("ascii")

    if isinstance(obj, list):
        return [sanitize_for_storage(v, depth+1) for v in obj]

    if isinstance(obj, tuple):
        return tuple(sanitize_for_storage(v, depth+1) for v in obj)

    if isinstance(obj, Mapping):
        return {
            strip_nul(str(k)): sanitize_for_storage(v, depth+1) for k, v in obj.items()
        }

    return obj

    # Size check for strings/bytes
    if isinstance(obj, (str, bytes, bytearray, memoryview)) and len(obj) > MAX_INPUT_SIZE:
        raise ValueError("Input size exceeds maximum allowed")

    if isinstance(obj, str):
        # Remove path traversal sequences
        clean = obj.replace("../", "").replace("..\\", "")
        return strip_nul(clean)

    if isinstance(obj, memoryview):
        obj = obj.tobytes()

    if isinstance(obj, (bytes, bytearray)):
        try:
            return strip_nul(bytes(obj).decode("utf-8"))
        except Exception:  # noqa: BLE001
            # Mark base64 content for proper handling
            return "[BASE64]" + base64.b64encode(bytes(obj)).decode("ascii")

    if isinstance(obj, list):
        return [sanitize_for_storage(v, depth+1) for v in obj]

    if isinstance(obj, tuple):
        return tuple(sanitize_for_storage(v, depth+1) for v in obj)

    if isinstance(obj, Mapping):
        return {
            strip_nul(str(k)): sanitize_for_storage(v, depth+1) for k, v in obj.items()
        }

    return obj
