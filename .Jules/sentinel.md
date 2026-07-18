## $(date +%Y-%m-%d) - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive data in `example_value` fields.
**Learning:** When generating share links, only specific fields should be exposed, but we export the entire `snapshot_json` from the database. A recursive sanitizer function must be applied to scrub IDOR/data leakage vectors before returning the JSON payload.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints.
## 2026-07-18 - Redact sensitive fields from public snapshot exports
**Vulnerability:** Snapshot JSON payloads often contain sensitive schema comments or connection example values. Exposing these completely in public share links could leak database credentials or internal business logic.
**Learning:** Even internal API payloads intended to be serialized dynamically (like SQL or markdown) might be exposed directly, requiring an explicit redaction pass.
**Prevention:** Always sanitize/redact schema snapshots using `_redact_sensitive_snapshot_fields` when handling unauthenticated share endpoints, before any further processing.
