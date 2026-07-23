## $(date +%Y-%m-%d) - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive data in `example_value` fields.
**Learning:** When generating share links, only specific fields should be exposed, but we export the entire `snapshot_json` from the database. A recursive sanitizer function must be applied to scrub IDOR/data leakage vectors before returning the JSON payload.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints.
## 2024-05-24 - [Data Leakage in Shared Snapshot Exports]
**Vulnerability:** Sensitive fields (comments, example values) were exposed in public shared snapshot exports (SQL, Markdown, LLM prompt) because `_redact_sensitive_snapshot_fields` was not applied before downstream serialization.
**Learning:** Must apply redaction before any downstream export/serialization functions.
**Prevention:** Ensure explicit redaction steps are implemented in all public export routes before processing data.
