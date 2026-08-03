## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-08-01 - Fix overly restrictive CORS configuration
**Vulnerability:** The backend CORS configuration (`allow_methods`) explicitly restricted allowed methods to `["GET", "POST", "OPTIONS"]` even though valid API routes use `PUT`, `PATCH`, and `DELETE`.
**Learning:** A global CORS allowlist must be derived from the complete API surface; otherwise browsers can block valid cross-origin operations even when the server route exists.
**Prevention:** Keep the explicit allowlist synchronized with every HTTP method used by the API and enforce it with focused preflight regression tests.
