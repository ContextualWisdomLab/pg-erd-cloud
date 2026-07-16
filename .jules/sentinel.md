## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2024-07-16 - [urllib.parse.urlsplit fails to extract netloc on DSNs without '://']
**Vulnerability:** DSN redaction logic bypassed on strings formatted like `postgres:user:password@host/db`.
**Learning:** `urllib.parse.urlsplit` fails to populate `netloc` when a non-standard URI lacks `://` but contains `:`. In this scenario, credentials are provided in the `path` instead, which skips extraction for redaction purposes. This behavior causes secrets from non-standard DSNs to leak into error messages.
**Prevention:** Always include a fallback to split on `:` and inject a dummy scheme (like `http://`) into such DSNs before parsing with `urlsplit` to ensure secrets are accurately extracted and masked.
