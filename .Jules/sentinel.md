## 2026-07-14 - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive data in `example_value` fields.
**Learning:** When generating share links, only specific fields should be exposed, but we export the entire `snapshot_json` from the database. A recursive sanitizer function must be applied to scrub IDOR/data leakage vectors before returning the JSON payload.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints.

## 2026-07-14 - [CRITICAL] Fix Data Leak in Public Export Endpoints
**Vulnerability:** Unauthenticated share link endpoints for SQL export, DB reversing spec, and index design spec were directly passing un-redacted snapshot JSON data to the generators. This could expose sensitive metadata like `comment`, `relation_comment`, `column_comment`, and `example_value`.
**Learning:** Even when exposing data through format transformers (like SQL generators or LLM prompts), any sensitive metadata fields included in the base JSON payload can leak if not explicitly redacted before transformation.
**Prevention:** Always apply the `_redact_sensitive_snapshot_fields` utility (or equivalent redaction logic) to JSON payloads before passing them to any export or transformation function exposed via unauthenticated endpoints.
