## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-08-26 - [Strix CI Resilience]
**Vulnerability:** The Strix CI job can fail due to AI provider availability issues (like rate limits, token caps, or API model retirements). This causes the workflow to exit non-zero without producing an actionable vulnerability report.
**Learning:** These failures (`exit code 1` from the provider timeout or exhaustion) are infrastructure issues, not security issues in the PR's code. Retrying with different models (e.g., `openai-direct/gpt-5.4` instead of `nvidia/llama-3.3-nemotron-super-49b-v1.5`) often works around transient errors, but sustained failure blocks PR progression.
**Prevention:** If a Strix workflow fails with "provider/backend was unavailable", understand that this is an external API failure. The job should ideally be rerun by a repository administrator. The codebase itself is not at fault.
