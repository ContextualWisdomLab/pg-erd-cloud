## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Generating Lockfiles with Hashes for Secure Dependency Resolution
**Learning:** When using `uv pip compile` to generate `requirements.lock` and `requirements-dev.lock`, the standard execution does not include package hashes. This causes CI `dependency-review` checks or `pip install --require-hashes` deployments to fail.
**Action:** Always append the `--generate-hashes` flag when running `uv pip compile` to ensure secure hash-locked dependencies (e.g., `uv pip compile pyproject.toml -o requirements.lock --generate-hashes`).
