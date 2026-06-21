with open("backend/app/sanitize.py", "r") as f:
    content = f.read()

strix_patch = """
MAX_RECURSION_DEPTH = 10
MAX_INPUT_SIZE = 10_000  # 10KB

def sanitize_for_storage(obj: object, depth: int = 0) -> object:
    \"\"\"Recursively sanitize strings for DB storage.

    - Removes NUL chars from *all* strings.
    - Converts bytes/memoryview to safe text (best-effort UTF-8; fallback base64).
    \"\"\"

    if depth > MAX_RECURSION_DEPTH:
        raise ValueError("Maximum recursion depth exceeded")

    if obj is None:
        return obj

    # Size check for strings/bytes
    if isinstance(obj, (str, bytes, bytearray, memoryview)) and len(obj) > MAX_INPUT_SIZE:
        raise ValueError("Input size exceeds maximum allowed")

    if isinstance(obj, str):
        # Remove path traversal sequences
        clean = obj.replace("../", "").replace("..\\\\", "")
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
"""

import re
content = re.sub(r'def sanitize_for_storage\(obj: object\) -> object:.*?(?=\n\n|\Z)', strix_patch.strip(), content, flags=re.DOTALL)

with open("backend/app/sanitize.py", "w") as f:
    f.write(content)
