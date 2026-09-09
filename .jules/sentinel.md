## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2024-09-09 - Transient Gateway Failures in Strix CI
**Vulnerability:** N/A (Infrastructure failure)
**Learning:** If the Strix CI job fails with annotations indicating `STRIX_PROVIDER_UNAVAILABLE: STRIX_SANDBOX_UNAVAILABLE: the last Strix attempt ended in the sandbox bootstrap (Caido proxy on 127.0.0.1 unreachable`, it is a transient error in the CI environment setting up the proxy, not a vulnerability in the codebase.
**Prevention:** Simply re-trigger the CI pipeline.
