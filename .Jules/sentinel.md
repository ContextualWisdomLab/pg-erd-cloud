## $(date +%Y-%m-%d) - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive data in `example_value` fields.
**Learning:** When generating share links, only specific fields should be exposed, but we export the entire `snapshot_json` from the database. A recursive sanitizer function must be applied to scrub IDOR/data leakage vectors before returning the JSON payload.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints.
## 2026-07-17 - Prevent sensitive data leakage in public share endpoints
**Vulnerability:** Public share endpoints (SQL export, Markdown exports) expose sensitive JSON fields (like example values and comments) that are supposedly redacted.
**Learning:** Redaction must be applied uniformly to the JSON payload before passing it to downstream renderers, not just on the JSON HTTP response payload.
**Prevention:** Apply _redact_sensitive_snapshot_fields centrally before any serialization or export logic.
