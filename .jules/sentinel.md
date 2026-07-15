## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Credential Leak via Malformed DSN (urlsplit behavior)
**Vulnerability:** Python's `urllib.parse.urlsplit` fails to correctly populate the `netloc` component (and thus the `password` property) for DSN strings that do not contain `://` (e.g., `postgres:user:password@host/db`) or use non-standard schemes with underscores (e.g., `snowflake_invalid://`). As a result, credentials embedded in these types of DSNs bypassed the backend redaction logic (`dsn_redaction.py`) and could be leaked into error messages.
**Learning:** `urlsplit` places credentials in the `path` component instead of `netloc` for non-standard DSNs lacking `://`, rendering standard property access (`parsed.password`) useless for extraction.
**Prevention:** In DSN redaction or validation utilities, always include a fallback mechanism to detect and modify the scheme (e.g., substituting with a valid one like `http://` before parsing) to ensure `urlsplit` properly extracts secrets from these edge-case connection strings.
