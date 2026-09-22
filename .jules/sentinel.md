## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2024-05-24 - Information Leakage During Authentication

**Vulnerability:** The authentication endpoints were returning highly specific error messages (e.g., "token revoked", "algorithm/key type mismatch", "invalid API key") when a token was rejected. This leaked internal state and validation logic to unauthenticated users, which could aid attackers in probing the system or identifying valid vs. invalid key shapes.
**Learning:** Detailed error messages that differentiate between reasons for authentication failure (e.g., missing claim vs revoked token) provide an oracle to attackers. The backend must present a uniform, generic failure response for all authentication rejections.
**Prevention:** All token and API key validation failures in the authentication flow (`backend/app/auth.py`) must raise a generic HTTP 401 exception with `detail="invalid token"`. Avoid returning specific failure reasons to the client.
