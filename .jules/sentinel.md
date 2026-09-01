## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-31 - Removing python-jose to Prevent ECDSA Timing Attacks
**Vulnerability:** The codebase depended on `python-jose`, which has a transitive dependency on `ecdsa`. The `ecdsa` package (version 0.19.2 and prior) is vulnerable to the Minerva timing attack on the P-256 curve (CVE-2024-23342, GHSA-wj6h-64fc-37mp), which allows attackers to recover the private key by observing cryptographic operation timing.
**Learning:** `python-jose` is effectively unmaintained and forces consumers to accept insecure legacy cryptographic dependencies, breaking CI security gates and endangering user data.
**Prevention:** Remove `python-jose` entirely and migrate to `PyJWT`, which leverages the actively maintained and secure `cryptography` backend, eliminating the `ecdsa` supply-chain risk.
