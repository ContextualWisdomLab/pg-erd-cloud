## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-05-14 - [Algorithmic Complexity DoS via API Keys in Rate Limiting]
**Vulnerability:** Rate limit subject extraction evaluated PBKDF2 API key hashes before the rate limit could be applied, leading to CPU exhaustion.
**Learning:** Expensive cryptographic operations like PBKDF2 must be deferred until after IP rate limits allow the request to proceed. Do not process static API keys as OIDC JWTs.
**Prevention:** Fall back to IP-based rate limiting for API keys early in the middleware pipeline to bypass expensive evaluation entirely.
