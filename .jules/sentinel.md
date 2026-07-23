## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2024-05-24 - [Fix DSN Redaction Bypass]
**Vulnerability:** DSNs without standard `://` scheme delimiters (e.g. `postgres:user:password@host/db`) caused `urllib.parse.urlsplit` to leave `netloc` empty and put credentials in the `path`, resulting in the `_password_candidates_from_dsn` function failing to extract and redact the password.
**Learning:** `urlsplit` is highly dependent on standard RFC URLs. If `://` is missing, it parses the entire string after the first `:` into the `path`. The existing fallback logic in the backend only accounted for non-standard schemes containing `://` (e.g., `invalid_scheme://`), leaving credentials exposed for scheme-less DSNs with just a `:`.
**Prevention:** Always implement a fallback to inject a valid dummy scheme (e.g., `http://`) and split by `:` for DSNs that lack `://` before relying on `urlsplit` to extract credentials for redaction.
