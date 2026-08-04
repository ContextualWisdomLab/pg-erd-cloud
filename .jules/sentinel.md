## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-03 - [DSN Redaction Bypass]
**Vulnerability:** DSN redaction logic bypassed credentials in `urllib.parse.urlsplit` for non-standard DSNs lacking `://` (e.g., `scheme:user:password@host/db`) because `netloc` was not populated.
**Learning:** `urlsplit` has varying behavior depending on whether a scheme includes underscores or lacks slashes, placing credentials in the `path` and skipping redaction routines that only look at `netloc`/`password`.
**Prevention:** Always fall back to splitting on `:` and substituting a generic scheme (like `http://`) before re-parsing with `urlsplit` if `netloc` is missing from the initial parse, ensuring embedded secrets are still correctly extracted and masked.
