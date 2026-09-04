## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Prevent Information Leakage During JWT Authentication
**Vulnerability:** JWT validation errors were exposing specific failure reasons (e.g., "unknown signing key", "token revoked", "algorithm/key type mismatch") in HTTP 401 response details.
**Learning:** Returning overly verbose authentication errors leaks internal state and validation logic, which attackers can use to probe or bypass the authentication mechanism.
**Prevention:** Always use generic error messages (e.g., "invalid token") for authentication failures, and ensure the test suite is configured to expect these generic responses to enforce this pattern.
## 2025-02-18 - Fix Strix Test Client Dependency Issue
**Vulnerability:** The Strix security scanner was failing closed due to an environment dependency issue missing `httpx2` while importing `openai/_types.py` and `starlette/testclient.py`.
**Learning:** External scanners like Strix that introspect the test environment can fail if optional dependencies used by `starlette.testclient` (which recently migrated from `httpx` to `httpx2`) are not fully installed in the `dev` dependency group.
**Prevention:** Add `httpx2` to the `dev` dependencies block in `pyproject.toml` to ensure the scanner environment fully bootstraps the mocked test clients without `ModuleNotFoundError`s.
